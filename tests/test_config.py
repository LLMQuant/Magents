import os
import tempfile

from src.utils.config import ConfigManager


class TestConfigManager:
    def test_default_global_config(self):
        cm = ConfigManager()
        config = cm.get_global_config()
        assert config["initial_capital"] == 1_000_000.0
        assert config["max_leverage"] == 2.0

    def test_default_strategy_configs(self):
        cm = ConfigManager()
        ma = cm.get_strategy_config("ma")
        assert "fast_window" in ma
        assert "slow_window" in ma

    def test_missing_strategy_returns_empty(self):
        cm = ConfigManager()
        config = cm.get_strategy_config("nonexistent")
        assert config == {}

    def test_load_yaml_config(self):
        yaml_content = """
global:
  initial_capital: 500000.0
strategies:
  ma:
    fast_window: 5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                cm = ConfigManager(f.name)
                assert cm.get_global_config()["initial_capital"] == 500_000.0
                assert cm.get_strategy_config("ma")["fast_window"] == 5
            finally:
                os.unlink(f.name)

    def test_set_strategy_param(self):
        cm = ConfigManager()
        cm.set_strategy_param("custom", "param1", 42)
        assert cm.get_strategy_config("custom")["param1"] == 42
