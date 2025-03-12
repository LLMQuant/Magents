#!/usr/bin/env python
"""
Multi-Strategy Backtest Example

This script demonstrates how to run a backtest with multiple trading strategies
using the Magents trading system.
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to the Python path if running from the examples directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.engine import BacktestingEngine
from src.core.portfolio import PortfolioManager
from src.data.feeds.base import CSVDataFeed
from src.data.management import DataManager
from src.risk.limits import DrawdownLimit, PositionLimit, ExposureLimit, LeverageLimit
from src.risk.manager import RiskManager
from src.utils.config import ConfigManager
from src.utils.visualization import BacktestVisualizer
from src.pods.strategies.factory import StrategyFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Run a multi-strategy backtest example."""
    # Setup configuration
    config_manager = ConfigManager('config/default.yaml')
    
    # Get global settings
    global_config = config_manager.get_global_config()
    
    # Setup strategy factory
    strategy_factory = StrategyFactory()
    
    # Define backtest parameters
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2020, 12, 31)
    instruments = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
    data_dir = 'data'
    strategy_names = ['ma', 'value', 'sentiment']
    
    # Setup data management
    data_manager = DataManager()
    
    # Register data feeds
    for instrument in instruments:
        data_file = os.path.join(data_dir, f"{instrument}.csv")
        
        # For example purposes, use mock data if the file doesn't exist
        if not os.path.exists(data_file):
            logging.warning(f"Data file not found for {instrument}: {data_file}")
            logging.info("Creating mock data for the example...")
            create_mock_data(data_file, start_date, end_date)
        
        feed = CSVDataFeed(
            name=instrument,
            file_path=data_file,
            date_column="date",
            instrument_column=None
        )
        data_manager.register_feed(instrument, feed)
    
    # Load data
    data_manager.load_data(start_date, end_date, instruments)
    
    # Setup portfolio management
    portfolio_manager = PortfolioManager()
    
    # Setup risk management
    risk_manager = RiskManager()
    
    # Add global risk limits
    risk_manager.add_global_limit(
        LeverageLimit(max_leverage=global_config.get('max_leverage', 2.0), severity="CRITICAL")
    )
    
    # Setup the backtesting engine
    engine = BacktestingEngine(
        data_manager=data_manager,
        portfolio_manager=portfolio_manager,
        risk_manager=risk_manager,
        start_date=start_date,
        end_date=end_date,
        initial_capital=global_config.get('initial_capital', 1000000.0)
    )
    
    # Load and register strategies
    for strategy_name in strategy_names:
        try:
            # Create strategy using factory
            strategy_config = config_manager.get_strategy_config(strategy_name)
            pod = strategy_factory.create_strategy(
                strategy_name=strategy_name,
                pod_id=f"{strategy_name.capitalize()}_Strategy",
                instruments=instruments,
                config_override=strategy_config
            )
            
            # Register the pod with the engine
            engine.register_pod(pod.pod_id, pod)
            
            # Set the event queue for the pod
            pod.set_event_queue(engine.event_queue)
            
            # Add pod-specific risk limits
            risk_manager.add_pod_limit(
                pod.pod_id,
                DrawdownLimit(max_drawdown=20.0, severity="CRITICAL")
            )
            
            for instrument in instruments:
                risk_manager.add_pod_limit(
                    pod.pod_id,
                    PositionLimit(max_position=10000, instrument=instrument)
                )
                
                risk_manager.add_pod_limit(
                    pod.pod_id,
                    ExposureLimit(max_exposure=30.0, instrument=instrument, is_percent=True)
                )
            
            logging.info(f"Registered strategy: {pod.pod_id}")
            
        except ValueError as e:
            logging.error(f"Error loading strategy '{strategy_name}': {e}")
    
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
    
    # Setup visualizer
    visualizer = BacktestVisualizer(title="Multi-Strategy Backtest Example")
    
    # Create output directory if it doesn't exist
    output_dir = 'results'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    visualizer.output_dir = output_dir
    
    # Generate visualizations
    visualizer.plot_equity_curves(
        equity_curves=equity_curves,
        save_path=os.path.join(output_dir, "equity_curves.png")
    )
    
    visualizer.plot_metrics_comparison(
        metrics=metrics,
        save_path=os.path.join(output_dir, "metrics_comparison.png")
    )
    
    visualizer.plot_heatmap(
        returns=returns,
        period="M",
        save_path=os.path.join(output_dir, "monthly_returns.png")
    )
    
    # Generate HTML report
    visualizer.generate_summary_report(
        metrics=metrics,
        equity_curves=equity_curves,
        output_path="multi_strategy_backtest_report.html"
    )
    
    logging.info(f"Generated HTML report at {os.path.join(output_dir, 'multi_strategy_backtest_report.html')}")
    logging.info("Backtest completed successfully")


def create_mock_data(file_path: str, start_date: datetime, end_date: datetime) -> None:
    """
    Create mock price data for demonstration purposes.
    
    Args:
        file_path: Path to save the CSV file
        start_date: Start date for the data
        end_date: End date for the data
    """
    import pandas as pd
    import numpy as np
    
    # Create date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='B')
    
    # Create a random walk for the price
    np.random.seed(42)  # For reproducibility
    price = 100.0
    prices = [price]
    
    for _ in range(1, len(date_range)):
        change_pct = np.random.normal(0.0005, 0.015)  # mean=0.05%, std=1.5%
        price = price * (1 + change_pct)
        prices.append(price)
    
    # Create a DataFrame
    df = pd.DataFrame({
        'date': date_range,
        'open': prices,
        'high': [p * (1 + np.random.uniform(0, 0.01)) for p in prices],
        'low': [p * (1 - np.random.uniform(0, 0.01)) for p in prices],
        'close': prices,
        'volume': [int(np.random.uniform(1000000, 10000000)) for _ in prices]
    })
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Save to CSV
    df.to_csv(file_path, index=False)
    logging.info(f"Created mock data file: {file_path}")


if __name__ == "__main__":
    main() 