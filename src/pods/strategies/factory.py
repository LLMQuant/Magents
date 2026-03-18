import logging
from typing import Dict, List, Any, Type, Optional

from src.pods.base import BasePod, MultiAgentPod
from src.utils.config import default_config_manager


class StrategyType:
    """Strategy classification types based on hedge fund industry standards."""
    EQUITY_LONG_SHORT = "equity_long_short"
    LONG_BIASED = "long_biased"
    EVENT_DRIVEN = "event_driven"
    MACRO = "macro"
    QUANT = "quant"
    MULTI_STRATEGY = "multi_strategy"

    @classmethod
    def get_all_types(cls) -> List[str]:
        """Get all available strategy types."""
        return [
            cls.EQUITY_LONG_SHORT,
            cls.LONG_BIASED,
            cls.EVENT_DRIVEN,
            cls.MACRO,
            cls.QUANT,
            cls.MULTI_STRATEGY
        ]


# Registry of strategy module paths and class names for lazy loading.
# Strategies that require additional dependencies (e.g. langchain) are
# still listed here so users can see what's available, but they will
# produce a clear error message at import time if deps are missing.
_BUILTIN_STRATEGIES: Dict[str, Dict[str, str]] = {
    # Equity Long/Short
    "ma": {
        "module": "src.pods.strategies.equity_long_short.moving_average",
        "class": "MovingAveragePod",
        "type": StrategyType.EQUITY_LONG_SHORT,
    },
    # Event Driven
    "congress": {
        "module": "src.pods.strategies.event_driven.congressional_trading",
        "class": "CongressionalTradingPod",
        "type": StrategyType.EVENT_DRIVEN,
    },
    # Long Biased
    "value": {
        "module": "src.pods.strategies.long_biased.value_investing",
        "class": "ValueInvestingPod",
        "type": StrategyType.LONG_BIASED,
    },
    # Quant
    "sentiment": {
        "module": "src.pods.strategies.quant.sentiment_trading",
        "class": "SentimentTradingPod",
        "type": StrategyType.QUANT,
    },
}


def _import_strategy_class(module_path: str, class_name: str) -> Type[BasePod]:
    """Lazily import a strategy class from its module path."""
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class StrategyFactory:
    """
    Factory class for creating and managing strategy pods.

    Provides a registry of available strategies, handles configuration,
    and instantiates strategies with consistent naming.
    """

    def __init__(self):
        """Initialize the strategy factory."""
        self._strategies: Dict[str, Type[BasePod]] = {}
        self._lazy_strategies: Dict[str, Dict[str, str]] = {}
        self._strategy_types: Dict[str, str] = {}
        self._register_builtin_strategies()

    def _register_builtin_strategies(self) -> None:
        """Register the built-in strategy types (lazy-loaded)."""
        for name, info in _BUILTIN_STRATEGIES.items():
            self._lazy_strategies[name] = info
            self._strategy_types[name] = info["type"]

    def _resolve_strategy(self, strategy_name: str) -> Type[BasePod]:
        """Resolve a strategy class, importing lazily if needed."""
        if strategy_name in self._strategies:
            return self._strategies[strategy_name]

        if strategy_name in self._lazy_strategies:
            info = self._lazy_strategies[strategy_name]
            cls = _import_strategy_class(info["module"], info["class"])
            self._strategies[strategy_name] = cls
            return cls

        raise ValueError(f"Strategy '{strategy_name}' not registered with the factory")

    def register_strategy(self, strategy_name: str, strategy_class: Type[BasePod], strategy_type: str) -> None:
        """
        Register a strategy type with the factory.

        Args:
            strategy_name: A unique identifier for the strategy
            strategy_class: The strategy class to register
            strategy_type: The type of strategy (e.g., equity_long_short, event_driven)
        """
        if strategy_name in self._strategies or strategy_name in self._lazy_strategies:
            logging.warning(f"Strategy '{strategy_name}' already registered. Overwriting.")

        self._strategies[strategy_name] = strategy_class
        self._strategy_types[strategy_name] = strategy_type

    def create_strategy(self,
                        strategy_name: str,
                        pod_id: Optional[str] = None,
                        instruments: Optional[List[str]] = None,
                        config_override: Optional[Dict[str, Any]] = None) -> BasePod:
        """
        Create a strategy pod instance.

        Args:
            strategy_name: The identifier of the strategy to create
            pod_id: Unique identifier for the pod (defaults to strategy_name + timestamp)
            instruments: List of instruments to trade
            config_override: Override default configuration parameters

        Returns:
            An instance of the strategy pod

        Raises:
            ValueError: If the strategy name is not registered
        """
        strategy_class = self._resolve_strategy(strategy_name)

        # Generate a pod ID if not provided
        if pod_id is None:
            import time
            pod_id = f"{strategy_name.capitalize()}_Strategy_{int(time.time())}"

        if instruments is None:
            instruments = []

        # Get strategy configuration
        strategy_config = default_config_manager.get_strategy_config(strategy_name).copy()

        # Override with any provided configuration
        if config_override:
            strategy_config.update(config_override)

        # Remove the 'type' key which is for classification, not construction
        strategy_config.pop("type", None)

        # Create the instance with the appropriate parameters based on strategy type
        if strategy_name == "ma":
            return strategy_class(
                pod_id=pod_id,
                instruments=instruments,
                fast_window=strategy_config.get('fast_window', 10),
                slow_window=strategy_config.get('slow_window', 30),
                position_size=strategy_config.get('position_size', 100)
            )
        else:
            return strategy_class(
                pod_id=pod_id,
                instruments=instruments,
                signal_threshold=strategy_config.get('signal_threshold', 0.6),
                position_size=strategy_config.get('position_size', 100),
                max_positions=strategy_config.get('max_positions', 5)
            )

    def get_available_strategies(self) -> List[str]:
        """Get a list of available strategy names."""
        names = set(self._strategies.keys()) | set(self._lazy_strategies.keys())
        return sorted(names)

    def get_strategies_by_type(self, strategy_type: str) -> List[str]:
        """Get a list of strategy names of a specific type."""
        return [name for name, type_ in self._strategy_types.items() if type_ == strategy_type]

    def get_strategy_type(self, strategy_name: str) -> str:
        """
        Get the type of a strategy.

        Raises:
            ValueError: If the strategy name is not registered
        """
        if strategy_name not in self._strategy_types:
            raise ValueError(f"Strategy '{strategy_name}' not registered with the factory")

        return self._strategy_types[strategy_name]


# Create a default factory instance
default_strategy_factory = StrategyFactory()
