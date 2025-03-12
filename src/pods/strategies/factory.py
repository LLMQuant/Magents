import logging
from typing import Dict, List, Any, Type, Optional

from src.pods.base import BasePod, MultiAgentPod
from src.pods.strategies.equity_long_short.moving_average import MovingAveragePod
from src.pods.strategies.long_biased.value_investing import ValueInvestingPod
from src.pods.strategies.quant.sentiment_trading import SentimentTradingPod
from src.pods.strategies.event_driven.congressional_trading import CongressionalTradingPod
from src.pods.strategies.long_biased.warren_buffett import WarrenBuffettPod
from src.pods.strategies.long_biased.ben_graham import BenGrahamPod
from src.pods.strategies.long_biased.charlie_munger import CharlieMungerPod
from src.pods.strategies.event_driven.bill_ackman import BillAckmanPod
from src.pods.strategies.long_biased.cathie_wood import CathieWoodPod
from src.pods.strategies.macro.stanley_druckenmiller import StanleyDruckenmillerPod
from src.pods.strategies.quant.fundamentals import FundamentalsPod
from src.pods.strategies.quant.sentiment import SentimentPod
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


class StrategyFactory:
    """
    Factory class for creating and managing strategy pods.
    
    This class simplifies the process of creating strategy pods by:
    1. Providing a registry of available strategies
    2. Handling configuration of strategy parameters
    3. Instantiating strategies with consistent naming
    """
    
    def __init__(self):
        """Initialize the strategy factory."""
        self._strategies = {}
        self._strategy_types = {}  # Maps strategy_name to strategy_type
        self._register_builtin_strategies()
    
    def _register_builtin_strategies(self) -> None:
        """Register the built-in strategy types."""
        # Equity Long/Short strategies
        self.register_strategy("ma", MovingAveragePod, StrategyType.EQUITY_LONG_SHORT)
        
        # Event Driven strategies
        self.register_strategy("congress", CongressionalTradingPod, StrategyType.EVENT_DRIVEN)
        self.register_strategy("ackman", BillAckmanPod, StrategyType.EVENT_DRIVEN)
        
        # Long Biased strategies
        self.register_strategy("value", ValueInvestingPod, StrategyType.LONG_BIASED)
        self.register_strategy("buffett", WarrenBuffettPod, StrategyType.LONG_BIASED)
        self.register_strategy("graham", BenGrahamPod, StrategyType.LONG_BIASED)
        self.register_strategy("munger", CharlieMungerPod, StrategyType.LONG_BIASED)
        self.register_strategy("wood", CathieWoodPod, StrategyType.LONG_BIASED)
        
        # Macro strategies
        self.register_strategy("druckenmiller", StanleyDruckenmillerPod, StrategyType.MACRO)
        
        # Quant strategies
        self.register_strategy("sentiment", SentimentTradingPod, StrategyType.QUANT)
        self.register_strategy("fundamentals", FundamentalsPod, StrategyType.QUANT)
    
    def register_strategy(self, strategy_name: str, strategy_class: Type[BasePod], strategy_type: str) -> None:
        """
        Register a strategy type with the factory.
        
        Args:
            strategy_name: A unique identifier for the strategy
            strategy_class: The strategy class to register
            strategy_type: The type of strategy (e.g., equity_long_short, event_driven)
        """
        if strategy_name in self._strategies:
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
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' not registered with the factory")
        
        # Generate a pod ID if not provided
        if pod_id is None:
            import time
            pod_id = f"{strategy_name.capitalize()}_Strategy_{int(time.time())}"
        
        # Default to empty list if instruments not provided
        if instruments is None:
            instruments = []
        
        # Get strategy configuration
        strategy_config = default_config_manager.get_strategy_config(strategy_name)
        
        # Override with any provided configuration
        if config_override:
            strategy_config.update(config_override)
        
        # Create the strategy instance
        strategy_class = self._strategies[strategy_name]
        
        # Create the instance with the appropriate parameters based on strategy type
        if strategy_name == "ma":
            return strategy_class(
                pod_id=pod_id,
                instruments=instruments,
                fast_window=strategy_config.get('fast_window', 10),
                slow_window=strategy_config.get('slow_window', 30),
                position_size=strategy_config.get('position_size', 100)
            )
        elif strategy_name in ["congress", "ackman", "value", "buffett", "graham", 
                              "munger", "wood", "sentiment", "fundamentals"]:
            return strategy_class(
                pod_id=pod_id,
                instruments=instruments,
                signal_threshold=strategy_config.get('signal_threshold', 0.6),
                position_size=strategy_config.get('position_size', 100),
                max_positions=strategy_config.get('max_positions', 5)
            )
        else:
            # For custom strategies, pass all config as kwargs
            return strategy_class(pod_id=pod_id, instruments=instruments, **strategy_config)
    
    def get_available_strategies(self) -> List[str]:
        """
        Get a list of available strategy names.
        
        Returns:
            List of registered strategy names
        """
        return list(self._strategies.keys())
    
    def get_strategies_by_type(self, strategy_type: str) -> List[str]:
        """
        Get a list of strategy names of a specific type.
        
        Args:
            strategy_type: The type of strategy to filter by
            
        Returns:
            List of strategy names of the specified type
        """
        return [name for name, type_ in self._strategy_types.items() if type_ == strategy_type]
    
    def get_strategy_type(self, strategy_name: str) -> str:
        """
        Get the type of a strategy.
        
        Args:
            strategy_name: The name of the strategy
            
        Returns:
            The type of the strategy
            
        Raises:
            ValueError: If the strategy name is not registered
        """
        if strategy_name not in self._strategy_types:
            raise ValueError(f"Strategy '{strategy_name}' not registered with the factory")
        
        return self._strategy_types[strategy_name]


# Create a default factory instance
default_strategy_factory = StrategyFactory() 