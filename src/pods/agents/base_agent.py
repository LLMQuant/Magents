from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from src.core.event import MarketDataEvent, SignalEvent, RiskEvent
from src.core.order import Order


class BaseAgent(ABC):
    """
    Base class for all agents within a trading pod.
    
    Agents are the individual components within a pod that handle specific
    responsibilities like signal generation, execution, or risk management.
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.pod = None  # Will be set by the pod when adding the agent
    
    def initialize(self, start_date: datetime) -> None:
        """
        Initialize the agent at the start of a backtest.
        
        Default implementation does nothing, but subclasses can override
        to perform initialization like loading models or setting up state.
        
        Parameters:
        - start_date: Start date of the backtest
        """
        pass
    
    def on_market_data(self, event: MarketDataEvent) -> None:
        """
        Process a market data event.
        
        Default implementation does nothing, but subclasses should override
        to implement their specific market data processing logic.
        
        Parameters:
        - event: Market data event to process
        """
        pass
    
    def on_signal(self, event: SignalEvent) -> None:
        """
        Process a signal event.
        
        Default implementation does nothing, but subclasses should override
        to implement their specific signal processing logic.
        
        Parameters:
        - event: Signal event to process
        """
        pass
    
    def on_order_status(self, order: Order) -> None:
        """
        Process an order status update.
        
        Default implementation does nothing, but subclasses can override
        to track order status changes.
        
        Parameters:
        - order: Order with updated status
        """
        pass
    
    def on_order_fill(self, order: Order, fill_price: float, fill_quantity: float) -> None:
        """
        Process an order fill.
        
        Default implementation does nothing, but subclasses can override
        to track fills and update internal state.
        
        Parameters:
        - order: Filled order
        - fill_price: Price at which the order was filled
        - fill_quantity: Quantity that was filled
        """
        pass
    
    def on_risk_event(self, event: RiskEvent) -> None:
        """
        Process a risk event.
        
        Default implementation does nothing, but subclasses can override
        to respond to risk alerts.
        
        Parameters:
        - event: Risk event to process
        """
        pass


class SignalAgent(BaseAgent):
    """
    An agent that generates trading signals based on market data.
    
    This is a base class for signal-generating agents. Specific implementations
    should override the on_market_data method to implement their signal generation logic.
    """
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id)
    
    def send_signal(self, instrument: str, signal_type: str, strength: float, 
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a trading signal through the pod.
        
        Parameters:
        - instrument: Instrument the signal pertains to
        - signal_type: Type of signal (e.g., 'LONG', 'SHORT', 'EXIT')
        - strength: Signal strength between -1 (strong sell) and 1 (strong buy)
        - metadata: Additional signal information
        """
        if not self.pod:
            return
        
        self.pod.send_signal(instrument, signal_type, strength, metadata)


class ExecutionAgent(BaseAgent):
    """
    An agent that executes trades based on trading signals.
    
    This is a base class for execution agents. Specific implementations
    should override the on_signal method to implement their execution logic.
    """
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id)
    
    def send_order(self, instrument: str, quantity: float, side: str, 
                  order_type: str = "MARKET", limit_price: Optional[float] = None) -> str:
        """
        Send an order through the pod.
        
        Parameters:
        - instrument: Instrument to trade
        - quantity: Quantity to trade
        - side: Buy or sell ('BUY' or 'SELL')
        - order_type: Type of order ('MARKET', 'LIMIT', etc.)
        - limit_price: Limit price for limit orders
        
        Returns the order ID.
        """
        if not self.pod:
            return ""
        
        from src.core.order import OrderSide, OrderType
        
        # Convert string side to enum
        order_side = OrderSide.BUY if side == 'BUY' else OrderSide.SELL
        
        # Convert string order type to enum
        try:
            order_type_enum = OrderType[order_type]
        except KeyError:
            order_type_enum = OrderType.MARKET
        
        return self.pod.send_order(
            instrument=instrument,
            quantity=quantity,
            side=order_side,
            order_type=order_type_enum,
            limit_price=limit_price
        )


class RiskAgent(BaseAgent):
    """
    An agent that monitors and manages risk within a pod.
    
    This is a base class for risk management agents. Specific implementations
    should override the relevant event handlers to implement their risk logic.
    """
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id)
        self.position_limits = {}  # Instrument -> max position size
        self.max_drawdown = None  # Maximum drawdown limit
    
    def set_position_limit(self, instrument: str, max_size: float) -> None:
        """
        Set a position limit for an instrument.
        
        Parameters:
        - instrument: Instrument to set limit for
        - max_size: Maximum position size (absolute)
        """
        self.position_limits[instrument] = max_size
    
    def set_max_drawdown(self, max_drawdown_pct: float) -> None:
        """
        Set a maximum drawdown limit.
        
        Parameters:
        - max_drawdown_pct: Maximum drawdown as a percentage (positive number)
        """
        self.max_drawdown = max_drawdown_pct
    
    def on_order_status(self, order: Order) -> None:
        """Check if order complies with position limits."""
        if order.instrument in self.position_limits:
            # This is a simplified check; a real implementation would
            # need to consider the current position and the order size
            limit = self.position_limits[order.instrument]
            if order.quantity > limit:
                # Log warning or take corrective action
                pass
    
    def on_risk_event(self, event: RiskEvent) -> None:
        """Respond to risk events."""
        # Example implementation might close positions or adjust strategy
        # based on the risk event
        if event.alert_type == 'DRAWDOWN_LIMIT' and self.pod:
            # Example: close all positions if drawdown limit is breached
            pass 