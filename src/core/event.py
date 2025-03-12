from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union


class EventType(Enum):
    """Types of events in the system."""
    MARKET_DATA = "MARKET_DATA"  # New market data (price, volume, etc.)
    ORDER = "ORDER"              # New order request
    FILL = "FILL"                # Order fill confirmation
    SIGNAL = "SIGNAL"            # Trading signal
    RISK = "RISK"                # Risk event (limit breach, etc.)
    SYSTEM = "SYSTEM"            # System event (start, stop, etc.)


@dataclass
class Event:
    """Base class for all events in the system."""
    type: EventType
    timestamp: datetime
    source: str  # Source of the event (e.g., pod name, data feed)


@dataclass
class MarketDataEvent(Event):
    """Event for new market data."""
    instrument: str
    data: Dict[str, Any]  # Dictionary containing price, volume, etc.
    
    def __post_init__(self):
        self.type = EventType.MARKET_DATA


@dataclass
class OrderEvent(Event):
    """Event for order requests."""
    instrument: str
    order_id: str
    quantity: float
    side: str  # 'BUY' or 'SELL'
    order_type: str  # 'MARKET', 'LIMIT', etc.
    limit_price: Optional[float] = None
    pod_id: Optional[str] = None  # Which pod/strategy submitted this order
    
    def __post_init__(self):
        self.type = EventType.ORDER


@dataclass
class FillEvent(Event):
    """Event for order fills."""
    order_id: str
    instrument: str
    quantity: float
    price: float
    side: str
    commission: float = 0.0
    slippage: float = 0.0
    pod_id: Optional[str] = None
    
    def __post_init__(self):
        self.type = EventType.FILL


@dataclass
class SignalEvent(Event):
    """Event for trading signals."""
    instrument: str
    signal_type: str  # e.g., 'LONG', 'SHORT', 'EXIT'
    strength: float  # Signal strength between -1 (strong sell) and 1 (strong buy)
    metadata: Dict[str, Any] = None  # Additional signal information
    
    def __post_init__(self):
        self.type = EventType.SIGNAL


@dataclass
class RiskEvent(Event):
    """Event for risk alerts or limit breaches."""
    alert_type: str  # e.g., 'POSITION_LIMIT', 'DRAWDOWN_LIMIT'
    severity: str  # 'INFO', 'WARNING', 'CRITICAL'
    details: Dict[str, Any]  # Details about the risk event
    pod_id: Optional[str] = None
    
    def __post_init__(self):
        self.type = EventType.RISK


class EventQueue:
    """Queue for processing events in the system."""
    
    def __init__(self):
        self.events = []
    
    def put(self, event: Event) -> None:
        """Add an event to the queue."""
        self.events.append(event)
    
    def get(self) -> Optional[Event]:
        """Get the next event from the queue."""
        if not self.empty():
            return self.events.pop(0)
        return None
    
    def empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self.events) == 0
    
    def size(self) -> int:
        """Get the size of the queue."""
        return len(self.events) 