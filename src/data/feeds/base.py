from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Set, Union

import pandas as pd


class DataFeed(ABC):
    """
    Abstract base class for all data feeds.
    
    A data feed is responsible for loading and preprocessing data
    from a specific source (CSV files, APIs, databases, etc.)
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def load_data(self, start_date: datetime, end_date: datetime, 
                 instruments: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Load data for the specified time period and instruments.
        
        Parameters:
        - start_date: Start date for the data
        - end_date: End date for the data
        - instruments: List of instrument IDs to load (None = all available)
        
        Returns a DataFrame with the loaded data.
        """
        pass
    
    @abstractmethod
    def get_available_instruments(self) -> List[str]:
        """
        Get list of all available instruments from this feed.
        
        Returns a list of instrument IDs.
        """
        pass
    
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess the loaded data.
        
        This default implementation performs basic preprocessing:
        - Ensures the index is a DatetimeIndex
        - Sorts by timestamp
        - Handles missing values
        
        Subclasses can override this method to add feed-specific preprocessing.
        """
        if data.empty:
            return data
        
        # Ensure the index is a DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'timestamp' in data.columns:
                data = data.set_index('timestamp')
            elif 'date' in data.columns:
                data = data.set_index('date')
        
        # Convert index to datetime if needed
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        
        # Sort by index
        data = data.sort_index()
        
        # Handle missing values
        data = self._handle_missing_values(data)
        
        return data
    
    def _handle_missing_values(self, data: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in the data."""
        # For numerical columns, fill NaNs with the previous value
        numeric_cols = data.select_dtypes(include=['float', 'int']).columns
        if not numeric_cols.empty:
            data[numeric_cols] = data[numeric_cols].fillna(method='ffill')
        
        return data


class CSVDataFeed(DataFeed):
    """
    A data feed that loads data from CSV files.
    
    Each CSV file contains data for a single instrument or multiple instruments.
    """
    
    def __init__(self, name: str, file_path: str, date_column: str = 'date', 
                instrument_column: Optional[str] = 'instrument',
                date_format: Optional[str] = None):
        """
        Initialize a CSV data feed.
        
        Parameters:
        - name: Name of the feed
        - file_path: Path to the CSV file
        - date_column: Name of the column containing dates
        - instrument_column: Name of the column containing instrument IDs (None if single instrument)
        - date_format: Format string for parsing dates (None for automatic detection)
        """
        super().__init__(name)
        self.file_path = file_path
        self.date_column = date_column
        self.instrument_column = instrument_column
        self.date_format = date_format
        self._data = None
        self._available_instruments = []
    
    def load_data(self, start_date: datetime, end_date: datetime, 
                 instruments: Optional[List[str]] = None) -> pd.DataFrame:
        """Load data from the CSV file."""
        # Load data if not already loaded
        if self._data is None:
            self._load_csv()
        
        # Filter by date range
        mask = (self._data.index >= start_date) & (self._data.index <= end_date)
        filtered_data = self._data[mask].copy()
        
        # Filter by instruments if applicable
        if instruments and self.instrument_column:
            filtered_data = filtered_data[filtered_data[self.instrument_column].isin(instruments)]
        
        return filtered_data
    
    def get_available_instruments(self) -> List[str]:
        """Get list of available instruments."""
        # Load data if not already loaded
        if self._data is None:
            self._load_csv()
        
        return self._available_instruments
    
    def _load_csv(self) -> None:
        """Load the CSV file into memory."""
        try:
            # Read the CSV file
            data = pd.read_csv(self.file_path)
            
            # Parse dates
            date_kwargs = {}
            if self.date_format:
                date_kwargs['format'] = self.date_format
            
            data[self.date_column] = pd.to_datetime(data[self.date_column], **date_kwargs)
            
            # Set index
            data = data.set_index(self.date_column)
            
            # Preprocess the data
            data = self.preprocess_data(data)
            
            # Store the data
            self._data = data
            
            # Get available instruments
            if self.instrument_column and self.instrument_column in data.columns:
                self._available_instruments = data[self.instrument_column].unique().tolist()
            else:
                # If no instrument column, assume single instrument
                # Use the feed name as the instrument ID
                self._available_instruments = [self.name]
                data[self.instrument_column] = self.name
            
        except Exception as e:
            raise ValueError(f"Error loading CSV file {self.file_path}: {e}")


class InMemoryDataFeed(DataFeed):
    """
    A data feed that uses in-memory pandas DataFrames.
    
    Useful for testing or when data is generated programmatically.
    """
    
    def __init__(self, name: str, data: pd.DataFrame, instrument_column: Optional[str] = 'instrument'):
        """
        Initialize an in-memory data feed.
        
        Parameters:
        - name: Name of the feed
        - data: DataFrame with the data
        - instrument_column: Name of the column containing instrument IDs (None if single instrument)
        """
        super().__init__(name)
        self.instrument_column = instrument_column
        
        # Preprocess the data
        self._data = self.preprocess_data(data.copy())
        
        # Get available instruments
        if instrument_column and instrument_column in self._data.columns:
            self._available_instruments = self._data[instrument_column].unique().tolist()
        else:
            # If no instrument column, assume single instrument
            self._available_instruments = [name]
            self._data[instrument_column] = name
    
    def load_data(self, start_date: datetime, end_date: datetime, 
                 instruments: Optional[List[str]] = None) -> pd.DataFrame:
        """Get data from the in-memory DataFrame."""
        # Filter by date range
        mask = (self._data.index >= start_date) & (self._data.index <= end_date)
        filtered_data = self._data[mask].copy()
        
        # Filter by instruments if applicable
        if instruments and self.instrument_column:
            filtered_data = filtered_data[filtered_data[self.instrument_column].isin(instruments)]
        
        return filtered_data
    
    def get_available_instruments(self) -> List[str]:
        """Get list of available instruments."""
        return self._available_instruments
    
    def update_data(self, new_data: pd.DataFrame) -> None:
        """
        Update the in-memory data with new data.
        
        This can be used to simulate real-time data updates.
        """
        # Preprocess the new data
        new_data = self.preprocess_data(new_data.copy())
        
        # Concatenate with existing data
        self._data = pd.concat([self._data, new_data])
        
        # Remove duplicates
        self._data = self._data[~self._data.index.duplicated(keep='last')]
        
        # Sort by index
        self._data = self._data.sort_index()
        
        # Update available instruments
        if self.instrument_column and self.instrument_column in self._data.columns:
            self._available_instruments = self._data[self.instrument_column].unique().tolist() 