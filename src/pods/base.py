import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src.core.event import Event, EventType, MarketDataEvent, OrderEvent, SignalEvent, RiskEvent
from src.core.order import Order, OrderSide, OrderType


class BasePod(ABC):
    """
    Base class for all trading pods.
    
    A trading pod represents an independent trading strategy team
    with its own agents, data processing, and decision making.
    """
    
    def __init__(self, pod_id: str, instruments: List[str]):
        self.pod_id = pod_id
        self.instruments = instruments
        self.logger = logging.getLogger(f"pod.{pod_id}")
        self.event_queue = None  # Set by the engine when registering the pod
    
    def set_event_queue(self, event_queue) -> None:
        """Set the event queue for this pod to send events to."""
        self.event_queue = event_queue
    
    @abstractmethod
    def initialize(self, start_date: datetime) -> None:
        """
        Initialize the pod at the start of a backtest.
        
        Parameters:
        - start_date: Start date of the backtest
        """
        pass
    
    @abstractmethod
    def on_market_data(self, event: MarketDataEvent) -> None:
        """
        Process a market data event.
        
        Parameters:
        - event: Market data event to process
        """
        pass
    
    def on_order_status(self, order: Order) -> None:
        """
        Process an order status update.
        
        Parameters:
        - order: Order with updated status
        """
        self.logger.info(f"Order {order.order_id} status: {order.status}")
    
    def on_order_fill(self, order: Order, fill_price: float, fill_quantity: float) -> None:
        """
        Process an order fill.
        
        Parameters:
        - order: Filled order
        - fill_price: Price at which the order was filled
        - fill_quantity: Quantity that was filled
        """
        self.logger.info(f"Order {order.order_id} filled: {fill_quantity} @ {fill_price}")
    
    def on_signal(self, event: SignalEvent) -> None:
        """
        Process a signal event.
        
        Parameters:
        - event: Signal event to process
        """
        self.logger.info(f"Received signal for {event.instrument}: {event.signal_type} ({event.strength})")
    
    def on_risk_event(self, event: RiskEvent) -> None:
        """
        Process a risk event.
        
        Parameters:
        - event: Risk event to process
        """
        self.logger.warning(f"Risk event: {event.alert_type} ({event.severity})")
    
    def send_order(self, instrument: str, quantity: float, side: OrderSide, 
                  order_type: OrderType = OrderType.MARKET, 
                  limit_price: Optional[float] = None) -> str:
        """
        Send an order to the market.
        
        Parameters:
        - instrument: Instrument to trade
        - quantity: Quantity to trade
        - side: Buy or sell
        - order_type: Type of order (market, limit, etc.)
        - limit_price: Limit price for limit orders
        
        Returns the order ID.
        """
        if self.event_queue is None:
            self.logger.error("Cannot send order: event queue not set")
            return ""
        
        order_id = str(uuid.uuid4())
        
        # Create order event
        event = OrderEvent(
            type=EventType.ORDER,
            timestamp=datetime.now(),
            source=self.pod_id,
            instrument=instrument,
            order_id=order_id,
            quantity=quantity,
            side=side.value,  # Convert enum to string
            order_type=order_type.value,  # Convert enum to string
            limit_price=limit_price,
            pod_id=self.pod_id
        )
        
        # Add to event queue
        self.event_queue.put(event)
        
        self.logger.info(f"Sent {side.value} order for {quantity} {instrument}")
        
        return order_id
    
    def send_signal(self, instrument: str, signal_type: str, strength: float, 
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a signal to other agents.
        
        Parameters:
        - instrument: Instrument the signal pertains to
        - signal_type: Type of signal (e.g., 'LONG', 'SHORT', 'EXIT')
        - strength: Signal strength between -1 (strong sell) and 1 (strong buy)
        - metadata: Additional signal information
        """
        if self.event_queue is None:
            self.logger.error("Cannot send signal: event queue not set")
            return
        
        if metadata is None:
            metadata = {}
        
        # Create signal event
        event = SignalEvent(
            type=EventType.SIGNAL,
            timestamp=datetime.now(),
            source=self.pod_id,
            instrument=instrument,
            signal_type=signal_type,
            strength=strength,
            metadata=metadata
        )
        
        # Add to event queue
        self.event_queue.put(event)
        
        self.logger.info(f"Sent {signal_type} signal for {instrument} (strength: {strength})")


class MultiAgentPod(BasePod):
    """
    A trading pod that contains multiple agents that work together.
    
    Each agent can have a specific role in the strategy (e.g., signal generation,
    execution, risk management) and they communicate through signals.
    """
    
    def __init__(self, pod_id: str, instruments: List[str]):
        super().__init__(pod_id, instruments)
        self.agents = {}  # Dictionary of agent_id -> agent instance
    
    def add_agent(self, agent_id: str, agent) -> None:
        """Add an agent to the pod."""
        self.agents[agent_id] = agent
        agent.pod = self  # Set reference to this pod
        self.logger.info(f"Added agent {agent_id} to pod {self.pod_id}")
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize all agents in the pod."""
        self.logger.info(f"Initializing pod {self.pod_id}")
        
        for agent_id, agent in self.agents.items():
            try:
                agent.initialize(start_date)
            except Exception as e:
                self.logger.error(f"Error initializing agent {agent_id}: {e}", exc_info=True)
    
    def on_market_data(self, event: MarketDataEvent) -> None:
        """Forward market data to all agents."""
        # Only process data for instruments we're interested in
        if event.instrument not in self.instruments:
            return
        
        for agent_id, agent in self.agents.items():
            try:
                agent.on_market_data(event)
            except Exception as e:
                self.logger.error(f"Error in agent {agent_id} processing market data: {e}", exc_info=True)
    
    def on_signal(self, event: SignalEvent) -> None:
        """Forward signals to all agents."""
        super().on_signal(event)
        
        for agent_id, agent in self.agents.items():
            try:
                agent.on_signal(event)
            except Exception as e:
                self.logger.error(f"Error in agent {agent_id} processing signal: {e}", exc_info=True)
    
    def on_order_status(self, order: Order) -> None:
        """Forward order status updates to all agents."""
        super().on_order_status(order)
        
        for agent_id, agent in self.agents.items():
            try:
                agent.on_order_status(order)
            except Exception as e:
                self.logger.error(f"Error in agent {agent_id} processing order status: {e}", exc_info=True)
    
    def on_order_fill(self, order: Order, fill_price: float, fill_quantity: float) -> None:
        """Forward order fills to all agents."""
        super().on_order_fill(order, fill_price, fill_quantity)
        
        for agent_id, agent in self.agents.items():
            try:
                agent.on_order_fill(order, fill_price, fill_quantity)
            except Exception as e:
                self.logger.error(f"Error in agent {agent_id} processing order fill: {e}", exc_info=True)
    
    def on_risk_event(self, event: RiskEvent) -> None:
        """Forward risk events to all agents."""
        super().on_risk_event(event)
        
        for agent_id, agent in self.agents.items():
            try:
                agent.on_risk_event(event)
            except Exception as e:
                self.logger.error(f"Error in agent {agent_id} processing risk event: {e}", exc_info=True) 