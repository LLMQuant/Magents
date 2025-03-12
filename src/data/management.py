import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd
import numpy as np

from src.data.feeds.base import DataFeed


class DataManager:
    """
    Central data management system that aggregates data from various feeds
    and provides a unified interface for accessing data.
    """
    
    def __init__(self):
        self.feeds: Dict[str, DataFeed] = {}
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.instruments: Set[str] = set()
        self.logger = logging.getLogger(__name__)
    
    def register_feed(self, feed_id: str, feed: DataFeed) -> None:
        """Register a data feed with the manager."""
        self.feeds[feed_id] = feed
        self.logger.info(f"Registered data feed: {feed_id}")
        
        # Add instruments from this feed to the set of available instruments
        feed_instruments = feed.get_available_instruments()
        self.instruments.update(feed_instruments)
        
        # Initialize cache for this feed
        self.data_cache[feed_id] = pd.DataFrame()
    
    def load_data(self, start_date: datetime, end_date: datetime, instruments: Optional[List[str]] = None) -> None:
        """Load data from all registered feeds for the specified time period."""
        if instruments is None:
            instruments = list(self.instruments)
        
        self.logger.info(f"Loading data from {start_date} to {end_date} for {len(instruments)} instruments")
        
        for feed_id, feed in self.feeds.items():
            try:
                # Load data from the feed
                feed_data = feed.load_data(start_date, end_date, instruments)
                
                # Store in cache
                self.data_cache[feed_id] = feed_data
                
                self.logger.info(f"Loaded {len(feed_data)} records from feed: {feed_id}")
            except Exception as e:
                self.logger.error(f"Error loading data from feed {feed_id}: {e}", exc_info=True)
    
    def get_data_for_timestamp(self, timestamp: datetime) -> Dict[str, Dict[str, Any]]:
        """
        Get all available data for a specific timestamp.
        Returns a dictionary mapping instrument IDs to data points.
        """
        result = {}
        
        for feed_id, feed_data in self.data_cache.items():
            # Skip empty feed data
            if feed_data.empty:
                continue
            
            # Get data for the timestamp
            try:
                # Try exact timestamp match
                if timestamp in feed_data.index:
                    timestamp_data = feed_data.loc[timestamp]
                    
                    # If we got a Series (single row), convert to DataFrame
                    if isinstance(timestamp_data, pd.Series):
                        timestamp_data = pd.DataFrame([timestamp_data])
                    
                    # Process each instrument's data
                    for _, row in timestamp_data.iterrows():
                        instrument = row.get('instrument')
                        if instrument:
                            # If this instrument already has data, update it
                            if instrument in result:
                                result[instrument].update(row.to_dict())
                            else:
                                result[instrument] = row.to_dict()
            except Exception as e:
                self.logger.warning(f"Error retrieving data from feed {feed_id} for timestamp {timestamp}: {e}")
        
        return result
    
    def get_historical_data(self, instrument: str, start_date: datetime, end_date: datetime, 
                           feed_id: Optional[str] = None) -> pd.DataFrame:
        """
        Get historical data for an instrument within a date range.
        If feed_id is specified, only get data from that feed.
        """
        result_data = []
        
        # If feed_id is specified, only look in that feed
        if feed_id and feed_id in self.data_cache:
            feeds_to_check = {feed_id: self.data_cache[feed_id]}
        else:
            feeds_to_check = self.data_cache
        
        for feed_id, feed_data in feeds_to_check.items():
            if feed_data.empty:
                continue
            
            try:
                # Filter by date range
                date_mask = (feed_data.index >= start_date) & (feed_data.index <= end_date)
                filtered_data = feed_data[date_mask]
                
                # Filter by instrument
                if 'instrument' in filtered_data.columns:
                    instrument_data = filtered_data[filtered_data['instrument'] == instrument]
                else:
                    # If no instrument column, assume the feed is specific to this instrument
                    instrument_data = filtered_data
                
                result_data.append(instrument_data)
            except Exception as e:
                self.logger.warning(f"Error retrieving historical data from feed {feed_id}: {e}")
        
        # Combine data from all feeds
        if result_data:
            combined_data = pd.concat(result_data)
            return combined_data.sort_index()
        
        return pd.DataFrame()
    
    def get_latest_data(self, instrument: str, n: int = 1, feed_id: Optional[str] = None) -> pd.DataFrame:
        """
        Get the latest n data points for an instrument.
        If feed_id is specified, only get data from that feed.
        """
        historical_data = self.get_historical_data(
            instrument, 
            datetime.min, 
            datetime.max, 
            feed_id
        )
        
        if historical_data.empty:
            return pd.DataFrame()
        
        # Sort by index (timestamp) and get the latest n rows
        sorted_data = historical_data.sort_index()
        return sorted_data.tail(n)
    
    def get_available_instruments(self) -> List[str]:
        """Get list of all available instruments across all feeds."""
        return list(self.instruments)
    
    def calculate_indicator(self, instrument: str, indicator_name: str, 
                          params: Dict[str, Any] = None) -> pd.Series:
        """
        Calculate a technical indicator for an instrument.
        
        Parameters:
        - instrument: The instrument ID
        - indicator_name: Name of the indicator (e.g., 'SMA', 'RSI')
        - params: Parameters for the indicator (e.g., {'window': 20})
        
        Returns a pandas Series with the indicator values.
        """
        if params is None:
            params = {}
        
        # Get historical data for the instrument
        data = self.get_historical_data(instrument, datetime.min, datetime.max)
        
        if data.empty:
            return pd.Series()
        
        # Ensure we have price data
        if 'close' not in data.columns and 'price' not in data.columns:
            return pd.Series()
        
        # Get price column
        price_col = 'close' if 'close' in data.columns else 'price'
        
        # Calculate the indicator based on the name
        if indicator_name == 'SMA':
            window = params.get('window', 20)
            return data[price_col].rolling(window=window).mean()
        
        elif indicator_name == 'EMA':
            window = params.get('window', 20)
            return data[price_col].ewm(span=window, adjust=False).mean()
        
        elif indicator_name == 'RSI':
            window = params.get('window', 14)
            delta = data[price_col].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=window).mean()
            avg_loss = loss.rolling(window=window).mean()
            
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))
        
        elif indicator_name == 'MACD':
            fast = params.get('fast', 12)
            slow = params.get('slow', 26)
            signal = params.get('signal', 9)
            
            fast_ema = data[price_col].ewm(span=fast, adjust=False).mean()
            slow_ema = data[price_col].ewm(span=slow, adjust=False).mean()
            macd = fast_ema - slow_ema
            return macd
        
        else:
            self.logger.warning(f"Unsupported indicator: {indicator_name}")
            return pd.Series()
    
    def merge_feeds(self, feed_ids: List[str], instruments: List[str]) -> pd.DataFrame:
        """
        Merge data from multiple feeds for a set of instruments.
        Useful for creating a consolidated dataset for analysis.
        """
        merged_data = []
        
        for feed_id in feed_ids:
            if feed_id not in self.data_cache:
                continue
            
            feed_data = self.data_cache[feed_id]
            
            if feed_data.empty:
                continue
            
            # Filter by instruments if applicable
            if 'instrument' in feed_data.columns:
                feed_data = feed_data[feed_data['instrument'].isin(instruments)]
            
            # Add feed identifier
            feed_data = feed_data.copy()
            feed_data['feed'] = feed_id
            
            merged_data.append(feed_data)
        
        if not merged_data:
            return pd.DataFrame()
        
        return pd.concat(merged_data)
    
    def resample_data(self, data: pd.DataFrame, freq: str) -> pd.DataFrame:
        """
        Resample time series data to a different frequency.
        
        Parameters:
        - data: DataFrane to resample
        - freq: Target frequency (e.g., '1H', '1D', '1W')
        
        Returns resampled DataFrame.
        """
        if data.empty:
            return pd.DataFrame()
        
        # Group by instrument if present
        if 'instrument' in data.columns:
            resampled_dfs = []
            
            for instrument, group in data.groupby('instrument'):
                numeric_cols = group.select_dtypes(include=[np.number]).columns
                
                # Set up resampling rules
                resampled = group.resample(freq).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'price': 'last'  # For non-OHLC data
                })
                
                # Handle non-price numeric columns
                for col in numeric_cols:
                    if col not in ['open', 'high', 'low', 'close', 'volume', 'price']:
                        resampled[col] = group[col].resample(freq).mean()
                
                # Add instrument column back
                resampled['instrument'] = instrument
                
                resampled_dfs.append(resampled)
            
            if resampled_dfs:
                return pd.concat(resampled_dfs)
            return pd.DataFrame()
        
        else:
            # No instrument column, just resample the data
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            
            resampled = data.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'price': 'last'  # For non-OHLC data
            })
            
            # Handle non-price numeric columns
            for col in numeric_cols:
                if col not in ['open', 'high', 'low', 'close', 'volume', 'price']:
                    resampled[col] = data[col].resample(freq).mean()
            
            return resampled 