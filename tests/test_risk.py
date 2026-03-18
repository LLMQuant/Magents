from datetime import datetime

from src.core.order import Order, OrderSide, OrderType
from src.core.portfolio import Portfolio
from src.risk.limits import DrawdownLimit, ExposureLimit, LeverageLimit, PositionLimit
from src.risk.manager import RiskManager


def _make_order(**kwargs):
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


class TestPositionLimit:
    def test_allows_within_limit(self):
        limit = PositionLimit(max_position=500, instrument="AAPL")
        portfolio = Portfolio("test", 1_000_000)
        order = _make_order(quantity=100)
        assert limit.validate_order(order, portfolio)

    def test_rejects_over_limit(self):
        limit = PositionLimit(max_position=50, instrument="AAPL")
        portfolio = Portfolio("test", 1_000_000)
        order = _make_order(quantity=100)
        assert not limit.validate_order(order, portfolio)

    def test_skips_different_instrument(self):
        limit = PositionLimit(max_position=50, instrument="MSFT")
        portfolio = Portfolio("test", 1_000_000)
        order = _make_order(quantity=100, instrument="AAPL")
        assert limit.validate_order(order, portfolio)


class TestDrawdownLimit:
    def test_allows_within_limit(self):
        limit = DrawdownLimit(max_drawdown=20.0)
        portfolio = Portfolio("test", 1_000_000)
        assert limit.validate_portfolio(portfolio)

    def test_rejects_over_limit(self):
        limit = DrawdownLimit(max_drawdown=10.0)
        portfolio = Portfolio("test", 1_000_000)
        # Simulate loss: spend cash without positions
        portfolio.cash = 800_000  # 20% drawdown
        assert not limit.validate_portfolio(portfolio)


class TestLeverageLimit:
    def test_allows_within_limit(self):
        limit = LeverageLimit(max_leverage=2.0)
        portfolio = Portfolio("test", 1_000_000)
        assert limit.validate_portfolio(portfolio)


class TestRiskManager:
    def test_validate_order_no_limits(self):
        rm = RiskManager()
        portfolio = Portfolio("test", 1_000_000)
        order = _make_order()
        assert rm.validate_order(order, portfolio)

    def test_validate_order_with_limit(self):
        rm = RiskManager()
        rm.add_pod_limit("test_pod", PositionLimit(max_position=50, instrument="AAPL"))
        portfolio = Portfolio("test_pod", 1_000_000)
        order = _make_order(quantity=100)
        assert not rm.validate_order(order, portfolio)

    def test_pod_status_halting(self):
        rm = RiskManager()
        assert rm.get_pod_status("pod1") == "ACTIVE"
        rm.set_pod_status("pod1", "HALTED")
        assert rm.get_pod_status("pod1") == "HALTED"
        rm.reset_pod_status("pod1")
        assert rm.get_pod_status("pod1") == "ACTIVE"
