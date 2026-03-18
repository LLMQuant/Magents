from datetime import datetime

from src.core.event import (
    Event,
    EventQueue,
    EventType,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    SignalEvent,
)


class TestEventQueue:
    def test_put_and_get(self):
        queue = EventQueue()
        event = Event(type=EventType.SYSTEM, timestamp=datetime.now(), source="test")
        queue.put(event)
        assert queue.size() == 1
        assert queue.get() is event
        assert queue.empty()

    def test_empty_get_returns_none(self):
        queue = EventQueue()
        assert queue.get() is None

    def test_fifo_order(self):
        queue = EventQueue()
        e1 = Event(type=EventType.SYSTEM, timestamp=datetime.now(), source="first")
        e2 = Event(type=EventType.SYSTEM, timestamp=datetime.now(), source="second")
        queue.put(e1)
        queue.put(e2)
        assert queue.get() is e1
        assert queue.get() is e2


class TestMarketDataEvent:
    def test_type_is_set(self):
        event = MarketDataEvent(
            type=EventType.MARKET_DATA,
            timestamp=datetime.now(),
            source="test",
            instrument="AAPL",
            data={"close": 150.0},
        )
        assert event.type == EventType.MARKET_DATA
        assert event.instrument == "AAPL"


class TestOrderEvent:
    def test_type_is_set(self):
        event = OrderEvent(
            type=EventType.ORDER,
            timestamp=datetime.now(),
            source="test",
            instrument="AAPL",
            order_id="order-1",
            quantity=100,
            side="BUY",
            order_type="MARKET",
        )
        assert event.type == EventType.ORDER


class TestSignalEvent:
    def test_type_is_set(self):
        event = SignalEvent(
            type=EventType.SIGNAL,
            timestamp=datetime.now(),
            source="test",
            instrument="AAPL",
            signal_type="LONG",
            strength=0.8,
        )
        assert event.type == EventType.SIGNAL
        assert event.strength == 0.8
