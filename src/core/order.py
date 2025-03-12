from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union


class OrderStatus(Enum):
    """Order status enumeration."""
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"   # Partially filled
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"     # Execute at best available price
    LIMIT = "LIMIT"       # Execute at specified price or better
    STOP = "STOP"         # Market order when price reaches stop price
    STOP_LIMIT = "STOP_LIMIT"  # Limit order when price reaches stop price


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """Base class for all order types."""
    order_id: str
    instrument: str
    quantity: float
    side: OrderSide
    order_type: OrderType
    created_time: datetime
    pod_id: str
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
    def is_filled(self) -> bool:
        """Check if the order is completely filled."""
        return self.status == OrderStatus.FILLED
    
    def is_active(self) -> bool:
        """Check if the order is still active (not filled, cancelled, or rejected)."""
        return self.status in [OrderStatus.CREATED, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]
    
    def remaining_quantity(self) -> float:
        """Get the remaining quantity to be filled."""
        return self.quantity - self.filled_quantity


class OrderBook:
    """Simulated order book for backtesting."""
    
    def __init__(self):
        # Orders stored by instrument and then by order_id
        self.orders: Dict[str, Dict[str, Order]] = {}
        # Market data for each instrument
        self.market_data: Dict[str, Dict] = {}
    
    def add_order(self, order: Order) -> None:
        """Add an order to the order book."""
        if order.instrument not in self.orders:
            self.orders[order.instrument] = {}
        
        self.orders[order.instrument][order.order_id] = order
        order.status = OrderStatus.SUBMITTED
    
    def cancel_order(self, order_id: str, instrument: str) -> bool:
        """Cancel an order in the order book."""
        if instrument in self.orders and order_id in self.orders[instrument]:
            order = self.orders[instrument][order_id]
            if order.is_active():
                order.status = OrderStatus.CANCELLED
                return True
        return False
    
    def update_market_data(self, instrument: str, data: Dict) -> List[Tuple[Order, float, float]]:
        """
        Update market data for an instrument and process matching orders.
        Returns a list of (order, fill_price, fill_quantity) for filled orders.
        """
        if instrument not in self.market_data:
            self.market_data[instrument] = {}
        
        self.market_data[instrument].update(data)
        
        # If the instrument has no orders, nothing to match
        if instrument not in self.orders:
            return []
        
        fills = []
        
        # Get current price data
        current_data = self.market_data[instrument]
        if 'price' not in current_data:
            return []
        
        current_price = current_data['price']
        
        # Process orders for this instrument
        for order_id, order in list(self.orders[instrument].items()):
            if not order.is_active():
                continue
            
            fill_price = None
            fill_quantity = 0.0
            
            # Match based on order type
            if order.order_type == OrderType.MARKET:
                # Market orders fill at current price
                fill_price = current_price
                fill_quantity = order.remaining_quantity()
            
            elif order.order_type == OrderType.LIMIT:
                # Limit orders fill if price is favorable
                if (order.side == OrderSide.BUY and current_price <= order.limit_price) or \
                   (order.side == OrderSide.SELL and current_price >= order.limit_price):
                    fill_price = current_price
                    fill_quantity = order.remaining_quantity()
            
            elif order.order_type == OrderType.STOP:
                # Stop orders become market orders when stop price is reached
                if (order.side == OrderSide.BUY and current_price >= order.stop_price) or \
                   (order.side == OrderSide.SELL and current_price <= order.stop_price):
                    fill_price = current_price
                    fill_quantity = order.remaining_quantity()
            
            elif order.order_type == OrderType.STOP_LIMIT:
                # Stop-limit orders become limit orders when stop price is reached
                if (order.side == OrderSide.BUY and current_price >= order.stop_price) or \
                   (order.side == OrderSide.SELL and current_price <= order.stop_price):
                    # Now it acts like a limit order
                    if (order.side == OrderSide.BUY and current_price <= order.limit_price) or \
                       (order.side == OrderSide.SELL and current_price >= order.limit_price):
                        fill_price = current_price
                        fill_quantity = order.remaining_quantity()
            
            # If we have a fill, update order status and add to fills list
            if fill_price is not None and fill_quantity > 0:
                order.filled_quantity += fill_quantity
                
                # If fully filled, update status
                if order.filled_quantity >= order.quantity:
                    order.status = OrderStatus.FILLED
                else:
                    order.status = OrderStatus.PARTIAL
                
                # Update average fill price
                if order.filled_price is None:
                    order.filled_price = fill_price
                else:
                    # Calculate weighted average price
                    prev_fill_qty = order.filled_quantity - fill_quantity
                    order.filled_price = (
                        (order.filled_price * prev_fill_qty) + (fill_price * fill_quantity)
                    ) / order.filled_quantity
                
                fills.append((order, fill_price, fill_quantity))
        
        return fills
    
    def get_order(self, order_id: str, instrument: str) -> Optional[Order]:
        """Get an order from the order book."""
        if instrument in self.orders and order_id in self.orders[instrument]:
            return self.orders[instrument][order_id]
        return None
    
    def get_active_orders(self, instrument: Optional[str] = None) -> List[Order]:
        """Get all active orders, optionally filtered by instrument."""
        active_orders = []
        
        if instrument:
            # Get active orders for a specific instrument
            if instrument in self.orders:
                active_orders.extend([
                    order for order in self.orders[instrument].values() 
                    if order.is_active()
                ])
        else:
            # Get all active orders
            for instrument_orders in self.orders.values():
                active_orders.extend([
                    order for order in instrument_orders.values() 
                    if order.is_active()
                ])
        
        return active_orders 