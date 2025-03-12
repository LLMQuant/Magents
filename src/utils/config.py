import os
import json
import yaml
import logging
from typing import Dict, Any, List, Optional


class ConfigManager:
    """
    Manages configuration for the trading system and strategies.
    
    This class loads configuration from JSON or YAML files and provides
    access to global settings as well as strategy-specific parameters.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file (JSON or YAML)
        """
        self.config = {
            "global": {
                "initial_capital": 1000000.0,
                "max_leverage": 2.0,
                "transaction_cost": 0.001,  # 10 bps
                "slippage": 0.0005,         # 5 bps
            },
            "strategies": {}
        }
        
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
        
        # Load default strategy parameters
        self._load_default_strategy_params()
    
    def load_config(self, config_path: str) -> None:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to the configuration file
        """
        try:
            _, ext = os.path.splitext(config_path)
            
            if ext.lower() == '.json':
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)
            elif ext.lower() in ['.yaml', '.yml']:
                with open(config_path, 'r') as f:
                    loaded_config = yaml.safe_load(f)
            else:
                logging.error(f"Unsupported config file format: {ext}")
                return
            
            # Update the config dictionary
            if isinstance(loaded_config, dict):
                # Update global config
                if 'global' in loaded_config:
                    self.config['global'].update(loaded_config['global'])
                
                # Update strategy configs
                if 'strategies' in loaded_config:
                    for strategy_name, strategy_config in loaded_config['strategies'].items():
                        if strategy_name not in self.config['strategies']:
                            self.config['strategies'][strategy_name] = {}
                        self.config['strategies'][strategy_name].update(strategy_config)
        
        except Exception as e:
            logging.error(f"Error loading config file {config_path}: {e}")
    
    def _load_default_strategy_params(self) -> None:
        """Load default parameters for built-in strategies."""
        # Moving Average strategy defaults
        self.config['strategies']['ma'] = {
            'fast_window': 10,
            'slow_window': 30,
            'position_size': 100
        }
        
        # Congressional trading strategy defaults
        self.config['strategies']['congress'] = {
            'signal_threshold': 0.6,
            'position_size': 100,
            'max_positions': 5
        }
        
        # Value investing strategy defaults
        self.config['strategies']['value'] = {
            'signal_threshold': 0.6,
            'position_size': 100,
            'max_positions': 5
        }
        
        # Sentiment trading strategy defaults
        self.config['strategies']['sentiment'] = {
            'signal_threshold': 0.6,
            'position_size': 100,
            'max_positions': 5
        }
    
    def get_global_config(self) -> Dict[str, Any]:
        """
        Get global configuration parameters.
        
        Returns:
            Dictionary of global configuration parameters
        """
        return self.config['global']
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get configuration parameters for a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary of strategy-specific configuration parameters
        """
        if strategy_name in self.config['strategies']:
            return self.config['strategies'][strategy_name]
        else:
            logging.warning(f"No configuration found for strategy '{strategy_name}'. Using empty config.")
            return {}
    
    def set_strategy_param(self, strategy_name: str, param_name: str, value: Any) -> None:
        """
        Set a specific parameter for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            param_name: Name of the parameter
            value: Value to set
        """
        if strategy_name not in self.config['strategies']:
            self.config['strategies'][strategy_name] = {}
        
        self.config['strategies'][strategy_name][param_name] = value
    
    def save_config(self, file_path: str) -> None:
        """
        Save the current configuration to a file.
        
        Args:
            file_path: Path to save the configuration file
        """
        try:
            _, ext = os.path.splitext(file_path)
            
            if ext.lower() == '.json':
                with open(file_path, 'w') as f:
                    json.dump(self.config, f, indent=4)
            elif ext.lower() in ['.yaml', '.yml']:
                with open(file_path, 'w') as f:
                    yaml.dump(self.config, f, default_flow_style=False)
            else:
                logging.error(f"Unsupported config file format: {ext}")
        except Exception as e:
            logging.error(f"Error saving config to {file_path}: {e}")


# Create a default instance
default_config_manager = ConfigManager() 