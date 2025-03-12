import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd

from src.core.event import Event, EventQueue, EventType, MarketDataEvent, OrderEvent, FillEvent
from src.core.order import Order, OrderBook, OrderSide, OrderType, OrderStatus
from src.core.portfolio import PortfolioManager
from src.data.management import DataManager
from src.risk.manager import RiskManager


class BacktestingEngine:
    """Core backtesting engine that orchestrates the simulation."""
    
    def __init__(
        self,
        data_manager: DataManager,
        portfolio_manager: PortfolioManager,
        risk_manager: RiskManager,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 1000000.0,
    ):
        self.data_manager = data_manager
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        
        self.current_time = start_date
        self.is_running = False
        self.event_queue = EventQueue()
        self.order_book = OrderBook()
        
        # Registered pods (strategies)
        self.pods = {}
        
        # Statistics and metrics
        self.stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'rejected_orders': 0,
            'simulation_time': 0,
            'events_processed': 0,
        }
        
        # For tracking portfolio value over time
        self.portfolio_history = []
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
    def register_pod(self, pod_id: str, pod_instance: Any) -> None:
        """Register a trading pod with the engine."""
        self.pods[pod_id] = pod_instance
        # Create a portfolio for this pod
        self.portfolio_manager.create_portfolio(pod_id, self.initial_capital / len(self.pods))
        self.logger.info(f"Registered pod: {pod_id}")
    
    def run(self) -> None:
        """Run the backtest simulation."""
        self.logger.info(f"Starting backtest from {self.start_date} to {self.end_date}")
        
        start_time = time.time()
        self.is_running = True
        
        # Initialize all pods
        for pod_id, pod in self.pods.items():
            pod.initialize(self.start_date)
        
        # Main simulation loop
        try:
            while self.current_time <= self.end_date and self.is_running:
                # Get market data for the current timestamp
                market_data = self.data_manager.get_data_for_timestamp(self.current_time)
                
                if market_data:
                    # Create market data events
                    for instrument, data in market_data.items():
                        event = MarketDataEvent(
                            type=EventType.MARKET_DATA,
                            timestamp=self.current_time,
                            source="data_manager",
                            instrument=instrument,
                            data=data
                        )
                        self.event_queue.put(event)
                    
                    # Process all events in the queue until empty
                    self._process_events()
                    
                    # Record portfolio values at this timestamp
                    self._record_portfolio_values()
                
                # Move to the next timestamp
                self.current_time = self._get_next_timestamp()
        
        except Exception as e:
            self.logger.error(f"Error in backtest: {e}", exc_info=True)
            self.is_running = False
        
        # Finalize backtest
        end_time = time.time()
        self.stats['simulation_time'] = end_time - start_time
        
        self.logger.info(f"Backtest completed in {self.stats['simulation_time']:.2f} seconds")
        self.logger.info(f"Processed {self.stats['events_processed']} events")
        self.logger.info(f"Total orders: {self.stats['total_orders']}, "
                         f"filled: {self.stats['filled_orders']}, "
                         f"rejected: {self.stats['rejected_orders']}")
    
    def stop(self) -> None:
        """Stop the backtest simulation."""
        self.is_running = False
        self.logger.info("Backtest stopped")
    
    def _process_events(self) -> None:
        """Process all events in the queue for the current timestamp."""
        while not self.event_queue.empty():
            event = self.event_queue.get()
            
            if not event:
                continue
            
            self.stats['events_processed'] += 1
            
            # Process different event types
            if event.type == EventType.MARKET_DATA:
                self._process_market_data_event(event)
            
            elif event.type == EventType.ORDER:
                self._process_order_event(event)
            
            elif event.type == EventType.FILL:
                self._process_fill_event(event)
            
            elif event.type == EventType.SIGNAL:
                self._process_signal_event(event)
            
            elif event.type == EventType.RISK:
                self._process_risk_event(event)
    
    def _process_market_data_event(self, event: MarketDataEvent) -> None:
        """Process a market data event."""
        # Update order book with new market data
        instrument = event.instrument
        data = event.data
        
        # Extract price information for the order book
        price_data = {'price': data.get('close', data.get('price'))}
        fills = self.order_book.update_market_data(instrument, price_data)
        
        # Process any fills generated
        for order, fill_price, fill_quantity in fills:
            self._generate_fill_event(order, fill_price, fill_quantity)
        
        # Update market prices for portfolio valuation
        updated_prices = {instrument: price_data['price']}
        self.portfolio_manager.update_market_prices(updated_prices)
        
        # Send market data to all pods
        for pod_id, pod in self.pods.items():
            pod.on_market_data(event)
    
    def _process_order_event(self, event: OrderEvent) -> None:
        """Process an order event."""
        self.stats['total_orders'] += 1
        
        # Convert event to Order object
        order = Order(
            order_id=event.order_id,
            instrument=event.instrument,
            quantity=event.quantity,
            side=OrderSide.BUY if event.side == 'BUY' else OrderSide.SELL,
            order_type=OrderType[event.order_type],
            created_time=event.timestamp,
            pod_id=event.pod_id,
            limit_price=event.limit_price
        )
        
        # Check with risk manager if order is allowed
        if not self.risk_manager.validate_order(order, self.portfolio_manager.get_portfolio(order.pod_id)):
            self.logger.warning(f"Order rejected by risk manager: {order.order_id}")
            order.status = OrderStatus.REJECTED
            self.stats['rejected_orders'] += 1
            
            # Notify the pod that its order was rejected
            pod = self.pods.get(order.pod_id)
            if pod:
                pod.on_order_status(order)
            
            return
        
        # Add order to the order book
        self.order_book.add_order(order)
        
        # Notify the pod that its order was accepted
        pod = self.pods.get(order.pod_id)
        if pod:
            pod.on_order_status(order)
        
        # For market orders, we can try to fill immediately
        if order.order_type == OrderType.MARKET:
            instrument = order.instrument
            if instrument in self.order_book.market_data:
                price_data = self.order_book.market_data[instrument]
                fills = self.order_book.update_market_data(instrument, price_data)
                
                for filled_order, fill_price, fill_quantity in fills:
                    self._generate_fill_event(filled_order, fill_price, fill_quantity)
    
    def _process_fill_event(self, event: FillEvent) -> None:
        """Process a fill event."""
        self.stats['filled_orders'] += 1
        
        # Get the order
        order = self.order_book.get_order(event.order_id, event.instrument)
        if not order:
            self.logger.warning(f"Fill event for unknown order: {event.order_id}")
            return
        
        # Update portfolio with the fill
        self.portfolio_manager.process_fill(
            order,
            event.price,
            event.quantity,
            event.timestamp,
            event.commission
        )
        
        # Notify the pod about the fill
        pod = self.pods.get(order.pod_id)
        if pod:
            pod.on_order_fill(order, event.price, event.quantity)
    
    def _process_signal_event(self, event) -> None:
        """Process a signal event."""
        # Forward signal to the appropriate pod
        target_pod = self.pods.get(event.source)
        if target_pod:
            target_pod.on_signal(event)
    
    def _process_risk_event(self, event) -> None:
        """Process a risk event."""
        # Handle risk alerts and enforce risk limits
        if event.pod_id and event.pod_id in self.pods:
            # Pod-specific risk event
            pod = self.pods[event.pod_id]
            pod.on_risk_event(event)
            
            # For critical risk events, take action
            if event.severity == 'CRITICAL':
                if event.alert_type == 'DRAWDOWN_LIMIT':
                    self._handle_drawdown_breach(event.pod_id)
                elif event.alert_type == 'POSITION_LIMIT':
                    self._handle_position_limit_breach(event.pod_id, event.details.get('instrument'))
        else:
            # Global risk event affecting all pods
            for pod_id, pod in self.pods.items():
                pod.on_risk_event(event)
    
    def _generate_fill_event(self, order: Order, fill_price: float, fill_quantity: float) -> None:
        """Generate a fill event for an order."""
        # Calculate commission (simplified model)
        commission = self._calculate_commission(fill_price, fill_quantity)
        
        # Simulate slippage (simplified model)
        slippage = self._calculate_slippage(fill_price, fill_quantity)
        
        # Adjust fill price with slippage
        adjusted_price = fill_price
        if order.side == OrderSide.BUY:
            adjusted_price += slippage
        else:
            adjusted_price -= slippage
        
        # Create fill event
        event = FillEvent(
            type=EventType.FILL,
            timestamp=self.current_time,
            source="order_book",
            order_id=order.order_id,
            instrument=order.instrument,
            quantity=fill_quantity,
            price=adjusted_price,
            side='BUY' if order.side == OrderSide.BUY else 'SELL',
            commission=commission,
            slippage=slippage,
            pod_id=order.pod_id
        )
        
        self.event_queue.put(event)
    
    def _calculate_commission(self, price: float, quantity: float) -> float:
        """Calculate commission for a trade (simplified model)."""
        # Simple percentage-based commission model
        commission_rate = 0.001  # 0.1%
        return price * quantity * commission_rate
    
    def _calculate_slippage(self, price: float, quantity: float) -> float:
        """Calculate slippage for a trade (simplified model)."""
        # Simple percentage-based slippage model
        slippage_rate = 0.0005  # 0.05%
        return price * slippage_rate
    
    def _get_next_timestamp(self) -> datetime:
        """Get the next timestamp in the simulation."""
        # This can be customized based on the data frequency
        # For daily data:
        return self.current_time + timedelta(days=1)
        
        # For minute data:
        # return self.current_time + timedelta(minutes=1)
    
    def _record_portfolio_values(self) -> None:
        """Record portfolio values for historical tracking."""
        # Get values for all portfolios
        values = {
            pod_id: portfolio.total_value() 
            for pod_id, portfolio in self.portfolio_manager.portfolios.items()
        }
        
        # Add combined portfolio
        values['COMBINED'] = self.portfolio_manager.get_total_fund_value()
        
        # Add to history
        self.portfolio_history.append({
            'timestamp': self.current_time,
            **values
        })
    
    def _handle_drawdown_breach(self, pod_id: str) -> None:
        """Handle a drawdown limit breach by closing all positions."""
        self.logger.warning(f"Drawdown limit breached for pod {pod_id}, closing all positions")
        
        # Get the pod's portfolio
        portfolio = self.portfolio_manager.get_portfolio(pod_id)
        if not portfolio:
            return
        
        # Create market orders to close all positions
        positions_summary = portfolio.get_positions_summary()
        for _, position in positions_summary.iterrows():
            instrument = position['instrument']
            quantity = position['quantity']
            
            if quantity == 0:
                continue
            
            # Create an order to close the position
            side = OrderSide.SELL if quantity > 0 else OrderSide.BUY
            order_quantity = abs(quantity)
            
            order_id = str(uuid.uuid4())
            order_event = OrderEvent(
                type=EventType.ORDER,
                timestamp=self.current_time,
                source="risk_manager",
                instrument=instrument,
                order_id=order_id,
                quantity=order_quantity,
                side='SELL' if side == OrderSide.SELL else 'BUY',
                order_type='MARKET',
                pod_id=pod_id
            )
            
            self.event_queue.put(order_event)
    
    def _handle_position_limit_breach(self, pod_id: str, instrument: str) -> None:
        """Handle a position limit breach by reducing the position."""
        self.logger.warning(f"Position limit breached for pod {pod_id} on {instrument}")
        
        # Get the pod's portfolio
        portfolio = self.portfolio_manager.get_portfolio(pod_id)
        if not portfolio:
            return
        
        # Find the position
        positions_summary = portfolio.get_positions_summary()
        position = positions_summary[positions_summary['instrument'] == instrument]
        
        if position.empty:
            return
        
        quantity = position.iloc[0]['quantity']
        
        # Calculate reduction amount (reduce by 50%)
        reduction = quantity * 0.5
        
        if abs(reduction) < 1e-6:
            return
        
        # Create an order to reduce the position
        side = OrderSide.SELL if quantity > 0 else OrderSide.BUY
        order_quantity = abs(reduction)
        
        order_id = str(uuid.uuid4())
        order_event = OrderEvent(
            type=EventType.ORDER,
            timestamp=self.current_time,
            source="risk_manager",
            instrument=instrument,
            order_id=order_id,
            quantity=order_quantity,
            side='SELL' if side == OrderSide.SELL else 'BUY',
            order_type='MARKET',
            pod_id=pod_id
        )
        
        self.event_queue.put(order_event)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics for the backtest."""
        # Convert portfolio history to DataFrame
        history_df = pd.DataFrame(self.portfolio_history)
        
        if history_df.empty:
            return {}
        
        # Set timestamp as index
        history_df.set_index('timestamp', inplace=True)
        
        # Calculate returns
        returns = history_df.pct_change().dropna()
        
        metrics = {}
        
        # Calculate metrics for each pod and combined
        for column in returns.columns:
            pod_returns = returns[column]
            
            # Calculate metrics
            total_return = ((history_df[column].iloc[-1] / history_df[column].iloc[0]) - 1) * 100
            annualized_return = total_return * (252 / len(returns))
            volatility = pod_returns.std() * (252 ** 0.5) * 100
            sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
            
            # Calculate drawdowns
            cumulative_returns = (1 + pod_returns).cumprod()
            running_max = cumulative_returns.cummax()
            drawdowns = (cumulative_returns / running_max) - 1
            max_drawdown = drawdowns.min() * 100
            
            metrics[column] = {
                'total_return': total_return,
                'annualized_return': annualized_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'final_value': history_df[column].iloc[-1],
                'initial_value': history_df[column].iloc[0]
            }
        
        return metrics
    
    def get_equity_curves(self) -> pd.DataFrame:
        """Get equity curves for all pods and combined."""
        return pd.DataFrame(self.portfolio_history).set_index('timestamp') 