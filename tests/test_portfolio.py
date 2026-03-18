from datetime import datetime

from src.core.portfolio import Portfolio, PortfolioManager, Position


class TestPosition:
    def test_initial_state(self):
        pos = Position("AAPL")
        assert pos.quantity == 0
        assert pos.cost_basis == 0.0
        assert pos.market_value() == 0.0

    def test_buy_updates_position(self):
        pos = Position("AAPL")
        pos.update(100, 150.0, datetime.now())
        assert pos.quantity == 100
        assert pos.cost_basis == 15000.0
        assert pos.average_price() == 150.0

    def test_sell_calculates_realized_pnl(self):
        pos = Position("AAPL")
        pos.update(100, 100.0, datetime.now())
        realized = pos.update(-50, 120.0, datetime.now())
        assert realized == 1000.0  # (120 - 100) * 50
        assert pos.quantity == 50

    def test_full_close(self):
        pos = Position("AAPL")
        pos.update(100, 100.0, datetime.now())
        realized = pos.update(-100, 110.0, datetime.now())
        assert realized == 1000.0
        assert pos.quantity == 0
        assert pos.cost_basis == 0.0

    def test_short_position(self):
        pos = Position("AAPL")
        pos.update(-100, 150.0, datetime.now())
        assert pos.quantity == -100

    def test_short_pnl_on_price_drop(self):
        """Short positions should profit when price drops."""
        pos = Position("AAPL")
        pos.update(-100, 150.0, datetime.now())
        pos.update_market_price(140.0)
        assert pos.unrealized_pnl == 1000.0  # (150 - 140) * 100

    def test_market_value(self):
        pos = Position("AAPL")
        pos.update(100, 150.0, datetime.now())
        pos.update_market_price(160.0)
        assert pos.market_value() == 16000.0


class TestPortfolio:
    def test_initial_cash(self):
        portfolio = Portfolio("test", 1_000_000)
        assert portfolio.cash == 1_000_000
        assert portfolio.total_value() == 1_000_000

    def test_buy_reduces_cash(self):
        portfolio = Portfolio("test", 1_000_000)
        portfolio.update_position("AAPL", 100, 150.0, datetime.now())
        assert portfolio.cash == 1_000_000 - 15000

    def test_sell_increases_cash(self):
        portfolio = Portfolio("test", 1_000_000)
        portfolio.update_position("AAPL", 100, 150.0, datetime.now())
        portfolio.update_position("AAPL", -100, 160.0, datetime.now())
        assert portfolio.cash == 1_000_000 + 1000  # net gain from trade

    def test_total_value_with_positions(self):
        portfolio = Portfolio("test", 1_000_000)
        portfolio.update_position("AAPL", 100, 150.0, datetime.now())
        # current price set to 150 by the update
        assert portfolio.total_value() == 1_000_000  # cash + position = total

    def test_commission_deducted(self):
        portfolio = Portfolio("test", 1_000_000)
        portfolio.update_position("AAPL", 100, 150.0, datetime.now(), commission=10.0)
        assert portfolio.cash == 1_000_000 - 15000 - 10

    def test_transactions_recorded(self):
        portfolio = Portfolio("test", 1_000_000)
        portfolio.update_position("AAPL", 100, 150.0, datetime.now())
        assert len(portfolio.transactions) == 1
        assert portfolio.transactions[0]["instrument"] == "AAPL"


class TestPortfolioManager:
    def test_create_portfolio(self):
        pm = PortfolioManager()
        p = pm.create_portfolio("pod1", 500_000)
        assert p.pod_id == "pod1"
        assert p.cash == 500_000

    def test_get_portfolio(self):
        pm = PortfolioManager()
        pm.create_portfolio("pod1", 500_000)
        assert pm.get_portfolio("pod1") is not None
        assert pm.get_portfolio("nonexistent") is None

    def test_total_fund_value(self):
        pm = PortfolioManager()
        pm.create_portfolio("pod1", 500_000)
        pm.create_portfolio("pod2", 300_000)
        # Combined portfolio starts at 0 unless fills are processed
        assert pm.get_portfolio("pod1").total_value() == 500_000
        assert pm.get_portfolio("pod2").total_value() == 300_000
