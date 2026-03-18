from datetime import datetime

from src.core.order import Order, OrderBook, OrderSide, OrderStatus, OrderType


class TestOrder:
    def _make_order(self, **kwargs):
        defaults = dict(
            order_id="o1",
            instrument="AAPL",
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            created_time=datetime.now(),
            pod_id="test_pod",
        )
        defaults.update(kwargs)
        return Order(**defaults)

    def test_initial_state(self):
        order = self._make_order()
        assert order.status == OrderStatus.CREATED
        assert order.is_active()
        assert not order.is_filled()
        assert order.remaining_quantity() == 100

    def test_filled_order(self):
        order = self._make_order()
        order.status = OrderStatus.FILLED
        order.filled_quantity = 100
        assert order.is_filled()
        assert not order.is_active()
        assert order.remaining_quantity() == 0


class TestOrderBook:
    def _make_order(self, **kwargs):
        defaults = dict(
            order_id="o1",
            instrument="AAPL",
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            created_time=datetime.now(),
            pod_id="test_pod",
        )
        defaults.update(kwargs)
        return Order(**defaults)

    def test_add_order(self):
        book = OrderBook()
        order = self._make_order()
        book.add_order(order)
        assert order.status == OrderStatus.SUBMITTED
        assert book.get_order("o1", "AAPL") is order

    def test_cancel_order(self):
        book = OrderBook()
        order = self._make_order()
        book.add_order(order)
        assert book.cancel_order("o1", "AAPL")
        assert order.status == OrderStatus.CANCELLED

    def test_market_order_fill(self):
        book = OrderBook()
        order = self._make_order()
        book.add_order(order)

        fills = book.update_market_data("AAPL", {"price": 150.0})
        assert len(fills) == 1
        filled_order, price, qty = fills[0]
        assert price == 150.0
        assert qty == 100
        assert filled_order.status == OrderStatus.FILLED

    def test_limit_order_no_fill_when_unfavorable(self):
        book = OrderBook()
        order = self._make_order(
            order_type=OrderType.LIMIT, limit_price=140.0, side=OrderSide.BUY
        )
        book.add_order(order)

        fills = book.update_market_data("AAPL", {"price": 150.0})
        assert len(fills) == 0

    def test_limit_order_fills_when_favorable(self):
        book = OrderBook()
        order = self._make_order(
            order_type=OrderType.LIMIT, limit_price=160.0, side=OrderSide.BUY
        )
        book.add_order(order)

        fills = book.update_market_data("AAPL", {"price": 150.0})
        assert len(fills) == 1

    def test_get_active_orders(self):
        book = OrderBook()
        o1 = self._make_order(order_id="o1")
        o2 = self._make_order(order_id="o2")
        book.add_order(o1)
        book.add_order(o2)
        book.cancel_order("o1", "AAPL")

        active = book.get_active_orders("AAPL")
        assert len(active) == 1
        assert active[0].order_id == "o2"
