from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Union

from src.core.order import Order, OrderSide
from src.core.portfolio import Portfolio


class RiskLimit(ABC):
    """
    Abstract base class for all risk limits.
    
    Risk limits define constraints on trading that should be enforced
    by the risk manager.
    """
    
    def __init__(self, limit_type: str, severity: str = 'WARNING'):
        self.limit_type = limit_type
        self.severity = severity  # 'INFO', 'WARNING', 'CRITICAL'
    
    @abstractmethod
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """
        Validate an order against this risk limit.
        Returns True if the order is allowed, False otherwise.
        """
        pass
    
    @abstractmethod
    def validate_portfolio(self, portfolio: Portfolio) -> bool:
        """
        Validate a portfolio against this risk limit.
        Returns True if the portfolio is within limits, False otherwise.
        """
        pass
    
    @abstractmethod
    def breach_details(self, portfolio: Portfolio) -> Dict:
        """
        Get details about a limit breach for a portfolio.
        Returns a dictionary with details about the breach.
        """
        pass


class PositionLimit(RiskLimit):
    """
    Limit the maximum position size for an instrument.
    """
    
    def __init__(self, max_position: float, instrument: Optional[str] = None, 
                 severity: str = 'WARNING'):
        """
        Initialize a position limit.
        
        Parameters:
        - max_position: Maximum position size in absolute terms
        - instrument: Specific instrument this limit applies to (None for all)
        - severity: Severity of the limit breach
        """
        super().__init__('POSITION_LIMIT', severity)
        self.max_position = max_position
        self.instrument = instrument
    
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate an order against the position limit."""
        # Skip if this limit is for a different instrument
        if self.instrument and order.instrument != self.instrument:
            return True
        
        # Get current position in the instrument
        position = portfolio.positions.get(order.instrument)
        current_quantity = position.quantity if position else 0
        
        # Calculate new position after the order
        if order.side == OrderSide.BUY:
            new_quantity = current_quantity + order.quantity
        else:
            new_quantity = current_quantity - order.quantity
        
        # Check if the new position exceeds the limit
        return abs(new_quantity) <= self.max_position
    
    def validate_portfolio(self, portfolio: Portfolio) -> bool:
        """Validate a portfolio against the position limit."""
        if self.instrument:
            # Check specific instrument
            position = portfolio.positions.get(self.instrument)
            if position and abs(position.quantity) > self.max_position:
                return False
        else:
            # Check all positions
            for position in portfolio.positions.values():
                if abs(position.quantity) > self.max_position:
                    return False
        
        return True
    
    def breach_details(self, portfolio: Portfolio) -> Dict:
        """Get details about a position limit breach."""
        breached_instruments = []
        
        if self.instrument:
            # Check specific instrument
            position = portfolio.positions.get(self.instrument)
            if position and abs(position.quantity) > self.max_position:
                breached_instruments.append({
                    'instrument': self.instrument,
                    'quantity': position.quantity,
                    'limit': self.max_position
                })
        else:
            # Check all positions
            for instrument, position in portfolio.positions.items():
                if abs(position.quantity) > self.max_position:
                    breached_instruments.append({
                        'instrument': instrument,
                        'quantity': position.quantity,
                        'limit': self.max_position
                    })
        
        return {
            'limit_type': self.limit_type,
            'breached_instruments': breached_instruments
        }


class ExposureLimit(RiskLimit):
    """
    Limit the maximum exposure (market value) for an instrument or the portfolio.
    """
    
    def __init__(self, max_exposure: float, instrument: Optional[str] = None,
                 is_percent: bool = False, severity: str = 'WARNING'):
        """
        Initialize an exposure limit.
        
        Parameters:
        - max_exposure: Maximum exposure (absolute or percentage)
        - instrument: Specific instrument this limit applies to (None for all)
        - is_percent: If True, max_exposure is a percentage of portfolio value
        - severity: Severity of the limit breach
        """
        super().__init__('EXPOSURE_LIMIT', severity)
        self.max_exposure = max_exposure
        self.instrument = instrument
        self.is_percent = is_percent
    
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate an order against the exposure limit."""
        # Skip if this limit is for a different instrument
        if self.instrument and order.instrument != self.instrument:
            return True
        
        # Get current position in the instrument
        position = portfolio.positions.get(order.instrument)
        
        # If no position and no price data, we can't validate
        if not position or position.current_price is None:
            return True
        
        # Calculate current exposure
        current_exposure = position.market_value()
        
        # Calculate exposure change from the order
        exposure_change = order.quantity * position.current_price
        if order.side == OrderSide.SELL:
            exposure_change *= -1
        
        # Calculate new exposure
        new_exposure = current_exposure + exposure_change
        
        # Get the actual limit based on whether it's a percentage
        actual_limit = self.max_exposure
        if self.is_percent:
            portfolio_value = portfolio.total_value()
            if portfolio_value <= 0:
                return False  # Can't calculate percentage if portfolio value is not positive
            actual_limit = portfolio_value * (self.max_exposure / 100)
        
        # Check if the new exposure exceeds the limit
        return abs(new_exposure) <= actual_limit
    
    def validate_portfolio(self, portfolio: Portfolio) -> bool:
        """Validate a portfolio against the exposure limit."""
        # Get the actual limit based on whether it's a percentage
        actual_limit = self.max_exposure
        if self.is_percent:
            portfolio_value = portfolio.total_value()
            if portfolio_value <= 0:
                return True  # Edge case: if portfolio is empty or negative, no breach
            actual_limit = portfolio_value * (self.max_exposure / 100)
        
        if self.instrument:
            # Check specific instrument
            position = portfolio.positions.get(self.instrument)
            if position:
                exposure = position.market_value()
                if abs(exposure) > actual_limit:
                    return False
        else:
            # Check total exposure
            exposures = portfolio.get_exposure()
            total_exposure = sum(abs(exp) for exp in exposures.values())
            if total_exposure > actual_limit:
                return False
        
        return True
    
    def breach_details(self, portfolio: Portfolio) -> Dict:
        """Get details about an exposure limit breach."""
        breached_instruments = []
        
        # Get the actual limit based on whether it's a percentage
        actual_limit = self.max_exposure
        if self.is_percent:
            portfolio_value = portfolio.total_value()
            if portfolio_value <= 0:
                return {'limit_type': self.limit_type, 'breached_instruments': []}
            actual_limit = portfolio_value * (self.max_exposure / 100)
        
        if self.instrument:
            # Check specific instrument
            position = portfolio.positions.get(self.instrument)
            if position:
                exposure = position.market_value()
                if abs(exposure) > actual_limit:
                    breached_instruments.append({
                        'instrument': self.instrument,
                        'exposure': exposure,
                        'limit': actual_limit
                    })
        else:
            # Check all instruments
            exposures = portfolio.get_exposure()
            for instrument, exposure in exposures.items():
                if abs(exposure) > actual_limit:
                    breached_instruments.append({
                        'instrument': instrument,
                        'exposure': exposure,
                        'limit': actual_limit
                    })
            
            # Also check total exposure
            total_exposure = sum(abs(exp) for exp in exposures.values())
            if total_exposure > actual_limit:
                breached_instruments.append({
                    'instrument': 'TOTAL',
                    'exposure': total_exposure,
                    'limit': actual_limit
                })
        
        return {
            'limit_type': self.limit_type,
            'is_percent': self.is_percent,
            'breached_instruments': breached_instruments
        }


class DrawdownLimit(RiskLimit):
    """
    Limit the maximum drawdown for a portfolio.
    """
    
    def __init__(self, max_drawdown: float, severity: str = 'CRITICAL'):
        """
        Initialize a drawdown limit.
        
        Parameters:
        - max_drawdown: Maximum allowed drawdown as a positive percentage (e.g., 10 for 10%)
        - severity: Severity of the limit breach
        """
        super().__init__('DRAWDOWN_LIMIT', severity)
        self.max_drawdown = max_drawdown
    
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """
        Validate an order against the drawdown limit.
        
        This is a bit tricky as we don't know the future drawdown,
        but we can check if the portfolio is already in breach.
        """
        # Get current portfolio value and starting value
        current_value = portfolio.total_value()
        starting_value = portfolio.starting_cash
        
        if starting_value <= 0:
            return True  # Can't calculate drawdown if starting value is not positive
        
        # Calculate current drawdown
        current_drawdown = (current_value / starting_value - 1) * 100
        
        # If we're already in a drawdown beyond the limit, reject new orders
        return current_drawdown >= -self.max_drawdown
    
    def validate_portfolio(self, portfolio: Portfolio) -> bool:
        """Validate a portfolio against the drawdown limit."""
        # Get current portfolio value and starting value
        current_value = portfolio.total_value()
        starting_value = portfolio.starting_cash
        
        if starting_value <= 0:
            return True  # Can't calculate drawdown if starting value is not positive
        
        # Calculate current drawdown
        current_drawdown = (current_value / starting_value - 1) * 100
        
        # Check if drawdown exceeds the limit
        return current_drawdown >= -self.max_drawdown
    
    def breach_details(self, portfolio: Portfolio) -> Dict:
        """Get details about a drawdown limit breach."""
        current_value = portfolio.total_value()
        starting_value = portfolio.starting_cash
        
        if starting_value <= 0:
            return {
                'limit_type': self.limit_type,
                'max_drawdown': self.max_drawdown,
                'current_drawdown': 0,
                'portfolio_value': current_value
            }
        
        # Calculate current drawdown
        current_drawdown = (current_value / starting_value - 1) * 100
        
        return {
            'limit_type': self.limit_type,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': current_drawdown,
            'starting_value': starting_value,
            'current_value': current_value
        }


class LeverageLimit(RiskLimit):
    """
    Limit the maximum leverage (gross exposure / equity) for a portfolio.
    """
    
    def __init__(self, max_leverage: float, severity: str = 'WARNING'):
        """
        Initialize a leverage limit.
        
        Parameters:
        - max_leverage: Maximum allowed leverage ratio (e.g., 2 for 2:1 leverage)
        - severity: Severity of the limit breach
        """
        super().__init__('LEVERAGE_LIMIT', severity)
        self.max_leverage = max_leverage
    
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """Validate an order against the leverage limit."""
        # Get current portfolio value
        portfolio_value = portfolio.total_value()
        
        if portfolio_value <= 0:
            return False  # Can't have leverage with negative or zero equity
        
        # Get current positions
        positions_summary = portfolio.get_positions_summary()
        
        # Calculate current gross exposure
        current_exposure = positions_summary['market_value'].abs().sum() if not positions_summary.empty else 0
        
        # Calculate exposure change from the order
        position = portfolio.positions.get(order.instrument)
        if not position or position.current_price is None:
            return True  # Can't calculate without price data
        
        exposure_change = order.quantity * position.current_price
        
        # For sell orders, it depends on the current position
        if order.side == OrderSide.SELL:
            if position.quantity > order.quantity:
                # Reducing a long position
                exposure_change *= -1
            elif position.quantity < 0:
                # Adding to a short position
                exposure_change = abs(exposure_change)
            else:
                # Creating a new short position
                exposure_change = abs(exposure_change)
        
        # Calculate new gross exposure
        new_exposure = current_exposure + exposure_change
        
        # Calculate new leverage
        new_leverage = new_exposure / portfolio_value
        
        # Check if the new leverage exceeds the limit
        return new_leverage <= self.max_leverage
    
    def validate_portfolio(self, portfolio: Portfolio) -> bool:
        """Validate a portfolio against the leverage limit."""
        # Get current portfolio value
        portfolio_value = portfolio.total_value()
        
        if portfolio_value <= 0:
            return False  # Can't have leverage with negative or zero equity
        
        # Get current positions
        positions_summary = portfolio.get_positions_summary()
        
        # Calculate current gross exposure
        current_exposure = positions_summary['market_value'].abs().sum() if not positions_summary.empty else 0
        
        # Calculate current leverage
        current_leverage = current_exposure / portfolio_value
        
        # Check if the current leverage exceeds the limit
        return current_leverage <= self.max_leverage
    
    def breach_details(self, portfolio: Portfolio) -> Dict:
        """Get details about a leverage limit breach."""
        # Get current portfolio value
        portfolio_value = portfolio.total_value()
        
        if portfolio_value <= 0:
            return {
                'limit_type': self.limit_type,
                'max_leverage': self.max_leverage,
                'current_leverage': float('inf'),
                'portfolio_value': portfolio_value
            }
        
        # Get current positions
        positions_summary = portfolio.get_positions_summary()
        
        # Calculate current gross exposure
        current_exposure = positions_summary['market_value'].abs().sum() if not positions_summary.empty else 0
        
        # Calculate current leverage
        current_leverage = current_exposure / portfolio_value
        
        return {
            'limit_type': self.limit_type,
            'max_leverage': self.max_leverage,
            'current_leverage': current_leverage,
            'gross_exposure': current_exposure,
            'portfolio_value': portfolio_value
        } 