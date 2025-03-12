#!/usr/bin/env python
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any

import pandas as pd
import matplotlib.pyplot as plt

from src.core.engine import BacktestingEngine
from src.core.portfolio import PortfolioManager
from src.data.feeds.base import CSVDataFeed
from src.data.management import DataManager
from src.pods.base import BasePod
from src.risk.limits import DrawdownLimit, PositionLimit, ExposureLimit, LeverageLimit
from src.risk.manager import RiskManager
from src.utils.config import default_config_manager, ConfigManager
from src.utils.visualization import default_visualizer, BacktestVisualizer
from src.pods.strategies.factory import default_strategy_factory, StrategyType


def setup_logging(level: str = "INFO", log_file: str = None) -> None:
    """Set up logging configuration."""
    log_level = getattr(logging, level.upper())
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(level=log_level, format=log_format, handlers=handlers)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Multi-Agent Trading System")
    
    # Backtest configuration
    parser.add_argument(
        "--start-date", 
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"), 
        default=datetime(2020, 1, 1),
        help="Start date for the backtest (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", 
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"), 
        default=datetime(2021, 1, 1),
        help="End date for the backtest (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--initial-capital", 
        type=float, 
        default=1000000.0,
        help="Initial capital for the backtest"
    )
    
    # Data configuration
    parser.add_argument(
        "--data-dir", 
        type=str, 
        default="data",
        help="Directory containing data files"
    )
    parser.add_argument(
        "--instruments", 
        type=str, 
        default="AAPL,MSFT,GOOGL",
        help="Comma-separated list of instruments to trade"
    )
    
    # Strategy configuration
    parser.add_argument(
        "--strategies", 
        type=str, 
        default="ma",
        help="Comma-separated list of strategies to use (examples: ma, congress, buffett, graham, sentiment)"
    )
    parser.add_argument(
        "--strategy-type", 
        type=str, 
        choices=StrategyType.get_all_types(),
        default=None,
        help="Filter strategies by type (e.g., equity_long_short, event_driven, long_biased, macro, quant)"
    )
    
    # Configuration
    parser.add_argument(
        "--config", 
        type=str, 
        default=None,
        help="Path to configuration file (JSON or YAML)"
    )
    
    # Reporting
    parser.add_argument(
        "--report-title", 
        type=str, 
        default="Magents Backtest",
        help="Title for the backtest report"
    )
    parser.add_argument(
        "--report-dir", 
        type=str, 
        default="results",
        help="Directory to save backtest reports"
    )
    parser.add_argument(
        "--generate-report", 
        action="store_true",
        help="Generate an HTML report of the backtest results"
    )
    
    # Logging configuration
    parser.add_argument(
        "--log-level", 
        type=str, 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
        default="INFO",
        help="Logging level"
    )
    parser.add_argument(
        "--log-file", 
        type=str, 
        default=None,
        help="Log file path"
    )
    
    return parser.parse_args()


def load_strategies(strategy_names: List[str], instruments: List[str], strategy_type: str = None) -> Dict[str, BasePod]:
    """
    Load and initialize strategy pods using the factory.
    
    Parameters:
    - strategy_names: List of strategy names to load
    - instruments: List of instruments to trade
    - strategy_type: Filter strategies by type (optional)
    
    Returns a dictionary of pod_id -> pod_instance
    """
    pods = {}
    
    # If strategy_type is specified, filter available strategies to that type
    if strategy_type and not strategy_names:
        # Load all strategies of the specified type
        strategy_names = default_strategy_factory.get_strategies_by_type(strategy_type)
        logging.info(f"Loading all {strategy_type} strategies: {', '.join(strategy_names)}")
    elif strategy_type and strategy_names:
        # Filter the specified strategies to only include those of the specified type
        filtered_names = []
        for strategy in strategy_names:
            try:
                if default_strategy_factory.get_strategy_type(strategy) == strategy_type:
                    filtered_names.append(strategy)
                else:
                    logging.warning(f"Strategy '{strategy}' is not of type '{strategy_type}' and will be skipped")
            except ValueError:
                logging.error(f"Strategy '{strategy}' is not registered with the factory")
        
        strategy_names = filtered_names
        if not strategy_names:
            logging.warning(f"No strategies of type '{strategy_type}' found in the specified strategies")
    
    for strategy in strategy_names:
        try:
            # Create the strategy using the factory
            pod = default_strategy_factory.create_strategy(
                strategy_name=strategy,
                pod_id=f"{strategy.capitalize()}_Strategy",
                instruments=instruments
            )
            pods[pod.pod_id] = pod
            strategy_type_name = default_strategy_factory.get_strategy_type(strategy)
            logging.info(f"Successfully loaded strategy: {strategy} (Type: {strategy_type_name}) as {pod.pod_id}")
        except ValueError as e:
            logging.error(f"Error loading strategy '{strategy}': {e}")
    
    if not pods:
        if strategy_type:
            available = default_strategy_factory.get_strategies_by_type(strategy_type)
            logging.error(f"No valid strategies of type '{strategy_type}' loaded. Available {strategy_type} strategies: {', '.join(available)}")
        else:
            available = default_strategy_factory.get_available_strategies()
            logging.error(f"No valid strategies loaded. Available strategies: {', '.join(available)}")
        
        # Display available strategy types
        all_types = StrategyType.get_all_types()
        logging.info(f"Available strategy types: {', '.join(all_types)}")
    
    return pods


def run_backtest(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Run the backtest with the specified configuration.
    
    Parameters:
    - args: Command-line arguments
    
    Returns a dictionary with backtest results.
    """
    # Load custom configuration if provided
    if args.config:
        default_config_manager.load_config(args.config)
    
    # Override with command-line parameters
    if args.initial_capital:
        default_config_manager.config['global']['initial_capital'] = args.initial_capital
    
    # Parse instruments and strategies
    instruments = args.instruments.split(",")
    strategy_names = args.strategies.split(",")
    
    # Set up data management
    data_manager = DataManager()
    
    # Register data feeds
    for instrument in instruments:
        data_file = os.path.join(args.data_dir, f"{instrument}.csv")
        
        if os.path.exists(data_file):
            feed = CSVDataFeed(
                name=instrument,
                file_path=data_file,
                date_column="date",
                instrument_column=None  # Single instrument per file
            )
            data_manager.register_feed(instrument, feed)
        else:
            logging.warning(f"Data file not found for {instrument}: {data_file}")
    
    # Load data
    data_manager.load_data(args.start_date, args.end_date, instruments)
    
    # Set up portfolio management
    portfolio_manager = PortfolioManager()
    
    # Set up risk management
    risk_manager = RiskManager()
    
    # Get global configuration
    global_config = default_config_manager.get_global_config()
    
    # Add global risk limits
    risk_manager.add_global_limit(
        LeverageLimit(max_leverage=global_config.get('max_leverage', 2.0), severity="CRITICAL")
    )
    
    # Set up the backtesting engine
    engine = BacktestingEngine(
        data_manager=data_manager,
        portfolio_manager=portfolio_manager,
        risk_manager=risk_manager,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=global_config.get('initial_capital', 1000000.0)
    )
    
    # Load and register strategies
    pods = load_strategies(strategy_names, instruments, args.strategy_type)
    
    for pod_id, pod in pods.items():
        # Register the pod with the engine
        engine.register_pod(pod_id, pod)
        
        # Set the event queue for the pod
        pod.set_event_queue(engine.event_queue)
        
        # Add pod-specific risk limits
        risk_manager.add_pod_limit(
            pod_id,
            DrawdownLimit(max_drawdown=20.0, severity="CRITICAL")
        )
        
        for instrument in instruments:
            risk_manager.add_pod_limit(
                pod_id,
                PositionLimit(max_position=10000, instrument=instrument)
            )
            
            risk_manager.add_pod_limit(
                pod_id,
                ExposureLimit(max_exposure=30.0, instrument=instrument, is_percent=True)
            )
    
    # Run the backtest
    logging.info("Starting backtest")
    engine.run()
    
    # Get performance metrics
    metrics = engine.get_performance_metrics()
    
    # Get equity curves and calculate returns
    equity_curves = engine.get_equity_curves()
    returns = equity_curves.pct_change().fillna(0)
    
    # Print summary
    print("\n=== Backtest Summary ===")
    for pod_id, pod_metrics in metrics.items():
        print(f"\nPod: {pod_id}")
        print(f"  Total Return: {pod_metrics['total_return']:.2f}%")
        print(f"  Annualized Return: {pod_metrics['annualized_return']:.2f}%")
        print(f"  Volatility: {pod_metrics['volatility']:.2f}%")
        print(f"  Sharpe Ratio: {pod_metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {pod_metrics['max_drawdown']:.2f}%")
        print(f"  Final Value: ${pod_metrics['final_value']:.2f}")
    
    # Set up visualizer
    visualizer = BacktestVisualizer(title=args.report_title)
    visualizer.output_dir = args.report_dir
    
    # Create basic plots
    visualizer.plot_equity_curves(
        equity_curves=equity_curves,
        save_path=os.path.join(args.report_dir, "equity_curves.png")
    )
    
    visualizer.plot_metrics_comparison(
        metrics=metrics,
        save_path=os.path.join(args.report_dir, "metrics_comparison.png")
    )
    
    visualizer.plot_heatmap(
        returns=returns,
        period="M",
        save_path=os.path.join(args.report_dir, "monthly_returns.png")
    )
    
    # Generate HTML report if requested
    if args.generate_report:
        visualizer.generate_summary_report(
            metrics=metrics,
            equity_curves=equity_curves,
            output_path="backtest_report.html"
        )
        logging.info(f"Generated HTML report at {os.path.join(args.report_dir, 'backtest_report.html')}")
    
    # Return results
    return {
        "metrics": metrics,
        "equity_curves": equity_curves,
        "returns": returns
    }


def main() -> None:
    """Main entry point."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging
    setup_logging(args.log_level, args.log_file)
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.report_dir):
        os.makedirs(args.report_dir)
    
    try:
        # Run the backtest
        results = run_backtest(args)
        
        logging.info("Backtest completed successfully")
        
        # Exit successfully
        sys.exit(0)
    
    except Exception as e:
        logging.error(f"Error during backtest: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
