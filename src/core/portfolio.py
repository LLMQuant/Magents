from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import numpy as np

from src.core.order import Order, OrderSide


class Position:
    """Represents a position in a single instrument."""
    
    def __init__(self, instrument: str):
        self.instrument = instrument
        self.quantity = 0.0
        self.cost_basis = 0.0  # Total cost of the position
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.current_price = None
        self.trades = []  # List of (timestamp, quantity, price) tuples
    
    def update(self, quantity: float, price: float, timestamp: datetime) -> float:
        """
        Update the position with a new trade.
        Returns the realized PnL for this trade (if any).
        """
        realized_pnl = 0.0
        
        # Record the trade
        self.trades.append((timestamp, quantity, price))
        
        # If the trade reduces the position size (selling long or buying to cover short)
        if (self.quantity > 0 and quantity < 0) or (self.quantity < 0 and quantity > 0):
            # Calculate realized P&L for the closed portion
            if abs(quantity) <= abs(self.quantity):
                # Partial or complete close
                avg_price = self.cost_basis / self.quantity if self.quantity != 0 else 0
                realized_pnl = (price - avg_price) * min(abs(quantity), abs(self.quantity))
                if self.quantity < 0:
                    realized_pnl *= -1  # Short positions have inverse P&L
            else:
                # Close and reverse position
                avg_price = self.cost_basis / self.quantity if self.quantity != 0 else 0
                realized_pnl = (price - avg_price) * abs(self.quantity)
                if self.quantity < 0:
                    realized_pnl *= -1
        
        # Update position
        old_quantity = self.quantity
        new_quantity = old_quantity + quantity
        
        # Update cost basis
        if new_quantity != 0:
            if (old_quantity > 0 and quantity > 0) or (old_quantity < 0 and quantity < 0):
                # Adding to position, update cost basis
                self.cost_basis += quantity * price
            elif abs(quantity) >= abs(old_quantity):
                # Closing and possibly reversing position, reset cost basis
                self.cost_basis = (quantity + old_quantity) * price
            else:
                # Reducing position
                self.cost_basis = (self.cost_basis / old_quantity) * new_quantity
        else:
            # Position closed, reset cost basis
            self.cost_basis = 0.0
        
        self.quantity = new_quantity
        self.realized_pnl += realized_pnl
        
        # Update current price for unrealized P&L calculation
        self.current_price = price
        if self.quantity != 0 and self.current_price is not None:
            avg_cost = self.cost_basis / self.quantity
            self.unrealized_pnl = (self.current_price - avg_cost) * self.quantity
            if self.quantity < 0:
                self.unrealized_pnl *= -1
        else:
            self.unrealized_pnl = 0.0
        
        return realized_pnl
    
    def update_market_price(self, price: float) -> None:
        """Update current market price and recalculate unrealized P&L."""
        self.current_price = price
        if self.quantity != 0:
            avg_cost = self.cost_basis / self.quantity
            self.unrealized_pnl = (price - avg_cost) * self.quantity
            if self.quantity < 0:
                self.unrealized_pnl *= -1
        else:
            self.unrealized_pnl = 0.0
    
    def market_value(self) -> float:
        """Get current market value of the position."""
        if self.current_price is None:
            return 0.0
        return self.quantity * self.current_price
    
    def average_price(self) -> Optional[float]:
        """Get average price of the position."""
        if self.quantity == 0:
            return None
        return self.cost_basis / self.quantity


class Portfolio:
    """Represents a portfolio of positions for a trading pod."""
    
    def __init__(self, pod_id: str, initial_cash: float = 0.0):
        self.pod_id = pod_id
        self.positions: Dict[str, Position] = {}
        self.cash = initial_cash
        self.starting_cash = initial_cash
        self.transactions = []  # List of all transactions
    
    def update_position(self, instrument: str, quantity: float, price: float, 
                       timestamp: datetime, commission: float = 0.0) -> float:
        """
        Update a position with a new trade.
        Returns the realized PnL for this trade.
        """
        # Create position if it doesn't exist
        if instrument not in self.positions:
            self.positions[instrument] = Position(instrument)
        
        # Update cash
        self.cash -= quantity * price
        self.cash -= commission
        
        # Record transaction
        self.transactions.append({
            'timestamp': timestamp,
            'instrument': instrument,
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'cash_after': self.cash
        })
        
        # Update position and get realized P&L
        realized_pnl = self.positions[instrument].update(quantity, price, timestamp)
        
        return realized_pnl
    
    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Update market prices for all positions."""
        for instrument, price in prices.items():
            if instrument in self.positions:
                self.positions[instrument].update_market_price(price)
    
    def total_value(self) -> float:
        """Get total portfolio value (cash + positions)."""
        positions_value = sum(pos.market_value() for pos in self.positions.values())
        return self.cash + positions_value
    
    def total_pnl(self) -> float:
        """Get total P&L (realized + unrealized)."""
        realized = sum(pos.realized_pnl for pos in self.positions.values())
        unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        return realized + unrealized
    
    def get_positions_summary(self) -> pd.DataFrame:
        """Get a summary of all positions as a DataFrame."""
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for instrument, position in self.positions.items():
            if position.quantity != 0:  # Only include active positions
                data.append({
                    'instrument': instrument,
                    'quantity': position.quantity,
                    'avg_price': position.average_price(),
                    'current_price': position.current_price,
                    'market_value': position.market_value(),
                    'unrealized_pnl': position.unrealized_pnl,
                    'realized_pnl': position.realized_pnl
                })
        
        return pd.DataFrame(data)
    
    def get_exposure(self) -> Dict[str, float]:
        """Get exposure by instrument."""
        exposure = {}
        for instrument, position in self.positions.items():
            if position.current_price is not None and position.quantity != 0:
                exposure[instrument] = position.market_value()
        
        return exposure
    
    def get_transactions_df(self) -> pd.DataFrame:
        """Get all transactions as a DataFrame."""
        return pd.DataFrame(self.transactions)


class PortfolioManager:
    """Manages portfolios for all trading pods and the overall fund."""
    
    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}
        self.combined_portfolio = Portfolio("COMBINED")
    
    def create_portfolio(self, pod_id: str, initial_cash: float = 0.0) -> Portfolio:
        """Create a new portfolio for a pod."""
        self.portfolios[pod_id] = Portfolio(pod_id, initial_cash)
        return self.portfolios[pod_id]
    
    def get_portfolio(self, pod_id: str) -> Optional[Portfolio]:
        """Get a pod's portfolio."""
        return self.portfolios.get(pod_id)
    
    def process_fill(self, order: Order, fill_price: float, fill_quantity: float, 
                     timestamp: datetime, commission: float = 0.0) -> None:
        """Process an order fill by updating the relevant portfolio."""
        pod_id = order.pod_id
        
        if pod_id not in self.portfolios:
            raise ValueError(f"No portfolio found for pod_id: {pod_id}")
        
        # Convert to signed quantity based on side
        signed_quantity = fill_quantity
        if order.side == OrderSide.SELL:
            signed_quantity = -fill_quantity
        
        # Update pod's portfolio
        self.portfolios[pod_id].update_position(
            order.instrument, 
            signed_quantity,
            fill_price, 
            timestamp,
            commission
        )
        
        # Update combined portfolio (for overall fund tracking)
        self.combined_portfolio.update_position(
            order.instrument, 
            signed_quantity,
            fill_price, 
            timestamp,
            commission
        )
    
    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Update market prices for all portfolios."""
        for portfolio in self.portfolios.values():
            portfolio.update_market_prices(prices)
        
        self.combined_portfolio.update_market_prices(prices)
    
    def get_total_fund_value(self) -> float:
        """Get total value of all portfolios combined."""
        return self.combined_portfolio.total_value()
    
    def get_pod_allocations(self) -> Dict[str, float]:
        """Get allocation percentage per pod."""
        total_value = self.get_total_fund_value()
        if total_value == 0:
            return {pod_id: 0.0 for pod_id in self.portfolios}
        
        return {
            pod_id: portfolio.total_value() / total_value 
            for pod_id, portfolio in self.portfolios.items()
        }
    
    def get_exposures_by_instrument(self) -> Dict[str, Dict[str, float]]:
        """Get exposures by instrument and pod."""
        exposures = {}
        
        # Get each pod's exposure
        for pod_id, portfolio in self.portfolios.items():
            pod_exposure = portfolio.get_exposure()
            for instrument, exposure in pod_exposure.items():
                if instrument not in exposures:
                    exposures[instrument] = {}
                exposures[instrument][pod_id] = exposure
        
        return exposures
    
    def get_total_exposure_by_instrument(self) -> Dict[str, float]:
        """Get total exposure by instrument across all pods."""
        return self.combined_portfolio.get_exposure()
    
    def get_performance_summary(self) -> pd.DataFrame:
        """Get performance summary for all pods."""
        data = []
        
        for pod_id, portfolio in self.portfolios.items():
            start_value = portfolio.starting_cash
            current_value = portfolio.total_value()
            pnl = portfolio.total_pnl()
            
            data.append({
                'pod_id': pod_id,
                'starting_value': start_value,
                'current_value': current_value,
                'pnl': pnl,
                'return_pct': (pnl / start_value) * 100 if start_value > 0 else 0.0
            })
        
        # Add combined row
        combined = self.combined_portfolio
        start_value = combined.starting_cash
        current_value = combined.total_value()
        pnl = combined.total_pnl()
        
        data.append({
            'pod_id': 'COMBINED',
            'starting_value': start_value,
            'current_value': current_value,
            'pnl': pnl,
            'return_pct': (pnl / start_value) * 100 if start_value > 0 else 0.0
        })
        
        return pd.DataFrame(data) 