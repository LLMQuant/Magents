import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta


class BacktestVisualizer:
    """
    Visualizes backtest results with interactive charts and performance metrics.
    
    Provides methods to:
    1. Plot equity curves
    2. Visualize individual trades
    3. Show performance metrics
    4. Compare strategies
    5. Export visualizations to various formats
    """
    
    def __init__(self, title: str = "Backtest Results"):
        """
        Initialize the visualizer.
        
        Args:
            title: Main title for the visualizations
        """
        self.title = title
        self.output_dir = "results"
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def plot_equity_curves(self, 
                         equity_curves: pd.DataFrame, 
                         benchmark: Optional[pd.Series] = None,
                         include_drawdowns: bool = True,
                         figsize: Tuple[int, int] = (14, 8),
                         save_path: Optional[str] = None) -> None:
        """
        Plot equity curves for one or more strategies.
        
        Args:
            equity_curves: DataFrame with datetime index and columns for each strategy
            benchmark: Optional benchmark series to compare against
            include_drawdowns: Whether to include drawdown visualization
            figsize: Figure size (width, height)
            save_path: Path to save the figure, or None to display
        """
        plt.figure(figsize=figsize)
        
        # Plot strategy equity curves
        for column in equity_curves.columns:
            plt.plot(equity_curves.index, equity_curves[column], label=column)
        
        # Add benchmark if provided
        if benchmark is not None:
            plt.plot(benchmark.index, benchmark, label="Benchmark", linestyle="--", color="gray")
        
        # Format the plot
        plt.title(f"{self.title} - Equity Curves")
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value ($)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.gcf().autofmt_xdate()
        
        # Save or show the plot
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logging.info(f"Saved equity curve plot to {save_path}")
        else:
            plt.show()
        
        # If including drawdowns, create a separate drawdown plot
        if include_drawdowns:
            self._plot_drawdowns(equity_curves, 
                               benchmark=benchmark, 
                               figsize=figsize,
                               save_path=self._modify_path(save_path, "_drawdowns") if save_path else None)
    
    def _plot_drawdowns(self, 
                      equity_curves: pd.DataFrame, 
                      benchmark: Optional[pd.Series] = None,
                      figsize: Tuple[int, int] = (14, 6),
                      save_path: Optional[str] = None) -> None:
        """
        Plot drawdowns for the strategies.
        
        Args:
            equity_curves: DataFrame with datetime index and columns for each strategy
            benchmark: Optional benchmark series to compare against
            figsize: Figure size (width, height)
            save_path: Path to save the figure, or None to display
        """
        plt.figure(figsize=figsize)
        
        # Calculate and plot drawdowns for each strategy
        for column in equity_curves.columns:
            equity = equity_curves[column]
            drawdowns = self._calculate_drawdowns(equity)
            plt.plot(drawdowns.index, drawdowns, label=f"{column} Drawdown")
        
        # Add benchmark drawdown if provided
        if benchmark is not None:
            benchmark_drawdowns = self._calculate_drawdowns(benchmark)
            plt.plot(benchmark_drawdowns.index, benchmark_drawdowns, 
                   label="Benchmark Drawdown", linestyle="--", color="gray")
        
        # Format the plot
        plt.title(f"{self.title} - Drawdowns")
        plt.xlabel("Date")
        plt.ylabel("Drawdown (%)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Format y-axis as percentage
        plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.1%}"))
        
        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.gcf().autofmt_xdate()
        
        # Save or show the plot
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logging.info(f"Saved drawdown plot to {save_path}")
        else:
            plt.show()
    
    def plot_metrics_comparison(self, 
                             metrics: Dict[str, Dict[str, float]],
                             selected_metrics: Optional[List[str]] = None,
                             figsize: Tuple[int, int] = (14, 8),
                             save_path: Optional[str] = None) -> None:
        """
        Create a comparison chart of performance metrics across strategies.
        
        Args:
            metrics: Dictionary of strategy_name -> metric_dict
            selected_metrics: Optional list of metrics to display (defaults to common metrics)
            figsize: Figure size (width, height)
            save_path: Path to save the figure, or None to display
        """
        if not metrics:
            logging.warning("No metrics provided for comparison")
            return
        
        # Default metrics to display if none specified
        if selected_metrics is None:
            selected_metrics = [
                'total_return', 'annualized_return', 'sharpe_ratio', 
                'max_drawdown', 'volatility', 'win_rate'
            ]
        
        # Filter to metrics that exist in data
        available_metrics = []
        for metric in selected_metrics:
            if all(metric in strategy_metrics for strategy_metrics in metrics.values()):
                available_metrics.append(metric)
        
        if not available_metrics:
            logging.warning("None of the specified metrics are available in all strategies")
            return
        
        # Extract the metric values for each strategy
        strategies = list(metrics.keys())
        
        # Set up the figure with subplots
        fig, axes = plt.subplots(len(available_metrics), 1, figsize=figsize, sharex=True)
        if len(available_metrics) == 1:
            axes = [axes]  # Handle single metric case
        
        # Plot each metric
        for i, metric in enumerate(available_metrics):
            values = [metrics[strategy][metric] for strategy in strategies]
            
            # Create the bar chart
            bars = axes[i].bar(strategies, values)
            
            # Format the plot
            axes[i].set_title(f"{metric.replace('_', ' ').title()}")
            axes[i].grid(True, alpha=0.3)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                axes[i].annotate(f"{height:.2f}",
                               xy=(bar.get_x() + bar.get_width() / 2, height),
                               xytext=(0, 3),  # 3 points vertical offset
                               textcoords="offset points",
                               ha='center', va='bottom')
            
            # Format y-axis as percentage for certain metrics
            if metric in ['total_return', 'annualized_return', 'max_drawdown', 'volatility']:
                axes[i].yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.1f}%"))
        
        # Configure layout
        plt.tight_layout()
        fig.subplots_adjust(top=0.95)
        fig.suptitle(f"{self.title} - Performance Metrics Comparison", fontsize=16)
        
        # Save or show the plot
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logging.info(f"Saved metrics comparison plot to {save_path}")
        else:
            plt.show()
    
    def plot_heatmap(self, 
                   returns: pd.DataFrame, 
                   period: str = "M",
                   figsize: Tuple[int, int] = (14, 8),
                   save_path: Optional[str] = None) -> None:
        """
        Plot a heatmap of returns for a given period.
        
        Args:
            returns: DataFrame of daily returns with datetime index
            period: Resampling period ('M' for monthly, 'Y' for yearly)
            figsize: Figure size (width, height)
            save_path: Path to save the figure, or None to display
        """
        if returns.empty:
            logging.warning("No returns data provided for heatmap")
            return
        
        period_map = {
            'M': ('Month', '%b'),
            'Y': ('Year', '%Y')
        }
        
        if period not in period_map:
            logging.warning(f"Unsupported period '{period}' for heatmap. Using monthly.")
            period = 'M'
        
        period_name, date_format = period_map[period]
        
        plt.figure(figsize=figsize)
        
        # Process each strategy
        for col in returns.columns:
            strategy_returns = returns[col]
            
            # Create a new figure for each strategy
            plt.figure(figsize=figsize)
            
            # Convert to period returns
            if period == 'M':
                # Group by year and month
                strategy_returns.index = pd.to_datetime(strategy_returns.index)
                grouped = strategy_returns.groupby([strategy_returns.index.year, strategy_returns.index.month]).sum()
                
                # Reshape to a matrix (year x month)
                matrix = pd.DataFrame()
                years = sorted(set(strategy_returns.index.year))
                months = list(range(1, 13))
                
                for year in years:
                    row = []
                    for month in months:
                        try:
                            value = grouped.loc[(year, month)]
                            row.append(value)
                        except KeyError:
                            row.append(np.nan)
                    matrix[year] = row
                
                matrix.index = [datetime(2000, m, 1).strftime('%b') for m in months]
                
            elif period == 'Y':
                # Group by year
                strategy_returns.index = pd.to_datetime(strategy_returns.index)
                matrix = strategy_returns.groupby(strategy_returns.index.year).sum().T
            
            # Create heatmap
            plt.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=-0.1, vmax=0.1)
            
            # Add colorbar
            cbar = plt.colorbar()
            cbar.set_label('Return')
            
            # Add value annotations
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    value = matrix.iloc[i, j]
                    if not np.isnan(value):
                        text_color = 'white' if abs(value) > 0.05 else 'black'
                        plt.text(j, i, f"{value:.1%}", ha="center", va="center", color=text_color)
            
            # Format the plot
            plt.title(f"{self.title} - {col} {period_name}ly Returns")
            plt.ylabel(f"{period_name}")
            plt.xlabel("Year")
            
            # Set tick labels
            plt.yticks(range(matrix.shape[0]), matrix.index)
            plt.xticks(range(matrix.shape[1]), matrix.columns)
            
            # Save or show the plot
            strategy_save_path = self._modify_path(save_path, f"_{col}_heatmap") if save_path else None
            
            if strategy_save_path:
                plt.savefig(strategy_save_path, dpi=300, bbox_inches="tight")
                logging.info(f"Saved heatmap plot for {col} to {strategy_save_path}")
            else:
                plt.show()
    
    def plot_trades(self, 
                  trades: pd.DataFrame,
                  prices: pd.DataFrame,
                  instruments: Optional[List[str]] = None,
                  figsize: Tuple[int, int] = (14, 10),
                  save_path: Optional[str] = None) -> None:
        """
        Plot trades against price charts.
        
        Args:
            trades: DataFrame with trade information (datetime, instrument, side, price, size)
            prices: DataFrame with price data for each instrument
            instruments: Optional list of instruments to plot (defaults to all)
            figsize: Figure size (width, height)
            save_path: Path to save the figure, or None to display
        """
        if trades.empty or prices.empty:
            logging.warning("No trade or price data provided")
            return
        
        # Select instruments to plot
        if instruments is None:
            instruments = sorted(set(trades['instrument']) & set(prices.columns))
        else:
            # Filter to instruments that have both trade and price data
            instruments = sorted(set(instruments) & set(trades['instrument']) & set(prices.columns))
        
        if not instruments:
            logging.warning("No instruments with both trade and price data")
            return
        
        # Create subplots for each instrument
        n_plots = len(instruments)
        fig, axes = plt.subplots(n_plots, 1, figsize=(figsize[0], figsize[1] * n_plots // 2), sharex=True)
        
        # Handle single instrument case
        if n_plots == 1:
            axes = [axes]
        
        for i, instrument in enumerate(instruments):
            ax = axes[i]
            
            # Plot price data
            ax.plot(prices.index, prices[instrument], label='Price', color='blue', alpha=0.7)
            
            # Filter trades for this instrument
            instrument_trades = trades[trades['instrument'] == instrument].copy()
            
            if not instrument_trades.empty:
                # Plot buy trades
                buys = instrument_trades[instrument_trades['side'] == 'BUY']
                if not buys.empty:
                    ax.scatter(buys['datetime'], buys['price'], 
                             marker='^', s=100, color='green', label='Buy')
                
                # Plot sell trades
                sells = instrument_trades[instrument_trades['side'] == 'SELL']
                if not sells.empty:
                    ax.scatter(sells['datetime'], sells['price'], 
                             marker='v', s=100, color='red', label='Sell')
            
            # Format the plot
            ax.set_title(f"{instrument} Trades")
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Format y-axis
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"${y:.2f}"))
        
        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()
        
        # Configure layout
        plt.tight_layout()
        fig.subplots_adjust(top=0.95)
        fig.suptitle(f"{self.title} - Trading Activity", fontsize=16)
        
        # Save or show the plot
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logging.info(f"Saved trades plot to {save_path}")
        else:
            plt.show()
    
    def generate_summary_report(self, 
                              metrics: Dict[str, Dict[str, float]],
                              equity_curves: pd.DataFrame,
                              output_path: str = "backtest_report.html") -> None:
        """
        Generate an HTML summary report.
        
        Args:
            metrics: Dictionary of strategy_name -> metric_dict
            equity_curves: DataFrame with equity curves
            output_path: Path to save the HTML report
        """
        try:
            import jinja2
            
            # Create a basic HTML template
            template_str = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>{{ title }} - Backtest Report</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }
                    th { background-color: #f2f2f2; text-align: center; }
                    .header { text-align: left; }
                    h1, h2 { color: #333; }
                    .container { max-width: 1200px; margin: 0 auto; }
                    .metric-good { color: green; }
                    .metric-bad { color: red; }
                    img { max-width: 100%; height: auto; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>{{ title }} - Backtest Report</h1>
                    <p>Generated on {{ generation_date }}</p>
                    
                    <h2>Performance Metrics</h2>
                    <table>
                        <tr>
                            <th class="header">Metric</th>
                            {% for strategy in strategies %}
                            <th>{{ strategy }}</th>
                            {% endfor %}
                        </tr>
                        {% for metric in metrics_list %}
                        <tr>
                            <td class="header">{{ metric|replace('_', ' ')|title }}</td>
                            {% for strategy in strategies %}
                            <td class="{{ get_metric_class(metric, strategy_metrics[strategy][metric]) }}">
                                {{ format_metric(metric, strategy_metrics[strategy][metric]) }}
                            </td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </table>
                    
                    <h2>Equity Curves</h2>
                    <img src="equity_curves.png" alt="Equity Curves">
                    
                    <h2>Drawdowns</h2>
                    <img src="drawdowns.png" alt="Drawdowns">
                </div>
            </body>
            </html>
            """
            
            # Define helper functions for the template
            def format_metric(metric, value):
                if metric in ['total_return', 'annualized_return', 'max_drawdown', 'volatility']:
                    return f"{value:.2f}%"
                elif metric in ['sharpe_ratio', 'sortino_ratio']:
                    return f"{value:.2f}"
                elif metric in ['win_rate']:
                    return f"{value:.2f}%"
                else:
                    return f"{value}"
            
            def get_metric_class(metric, value):
                if metric in ['total_return', 'annualized_return', 'sharpe_ratio', 'sortino_ratio', 'win_rate']:
                    return "metric-good" if value > 0 else "metric-bad"
                elif metric in ['max_drawdown', 'volatility']:
                    return "metric-bad" if value < 0 else ""
                else:
                    return ""
            
            # Prepare data for the template
            strategies = list(metrics.keys())
            
            # Find common metrics across all strategies
            all_metrics = set()
            for strategy_metrics in metrics.values():
                all_metrics.update(strategy_metrics.keys())
            
            metrics_list = sorted(all_metrics)
            
            # Generate plots for the report
            self.plot_equity_curves(
                equity_curves=equity_curves,
                save_path=os.path.join(self.output_dir, "equity_curves.png")
            )
            
            self._plot_drawdowns(
                equity_curves=equity_curves,
                save_path=os.path.join(self.output_dir, "drawdowns.png")
            )
            
            # Render the template
            env = jinja2.Environment()
            env.globals['format_metric'] = format_metric
            env.globals['get_metric_class'] = get_metric_class
            template = env.from_string(template_str)
            
            html_output = template.render(
                title=self.title,
                generation_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                strategies=strategies,
                metrics_list=metrics_list,
                strategy_metrics=metrics
            )
            
            # Save the HTML file
            with open(os.path.join(self.output_dir, output_path), 'w') as f:
                f.write(html_output)
            
            logging.info(f"Generated summary report at {os.path.join(self.output_dir, output_path)}")
            
        except ImportError:
            logging.warning("Jinja2 not found. Install with 'pip install jinja2' to generate HTML reports.")
    
    def _calculate_drawdowns(self, equity: pd.Series) -> pd.Series:
        """
        Calculate drawdowns from an equity curve.
        
        Args:
            equity: Series of equity values
            
        Returns:
            Series of drawdown values (negative percentages)
        """
        # Calculate rolling maximum
        rolling_max = equity.cummax()
        
        # Calculate drawdowns
        drawdowns = (equity - rolling_max) / rolling_max
        
        return drawdowns
    
    def _modify_path(self, path: Optional[str], suffix: str) -> Optional[str]:
        """Add a suffix to a file path before the extension."""
        if path is None:
            return None
            
        base, ext = os.path.splitext(path)
        return f"{base}{suffix}{ext}"


# Create a default visualizer instance
default_visualizer = BacktestVisualizer() 