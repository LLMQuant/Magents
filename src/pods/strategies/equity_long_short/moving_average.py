import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.core.event import MarketDataEvent
from src.core.order import OrderSide, OrderType
from src.pods.agents.base_agent import SignalAgent, ExecutionAgent
from src.pods.base import MultiAgentPod


class MovingAverageSignalAgent(SignalAgent):
    """
    Agent that generates trading signals based on moving average crossovers.
    """
    
    def __init__(self, agent_id: str, fast_window: int = 10, slow_window: int = 30):
        super().__init__(agent_id)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.historical_data = {}  # Instrument -> DataFrame
        self.last_signal = {}  # Instrument -> last signal type
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.historical_data = {}
        self.last_signal = {}
    
    def on_market_data(self, event: MarketDataEvent) -> None:
        """Process market data and generate trading signals."""
        instrument = event.instrument
        
        # Initialize data structure if needed
        if instrument not in self.historical_data:
            self.historical_data[instrument] = []
            self.last_signal[instrument] = None
        
        # Extract price from the data
        price = event.data.get('close', event.data.get('price'))
        if price is None:
            return
        
        # Add to historical data
        self.historical_data[instrument].append({
            'timestamp': event.timestamp,
            'price': price
        })
        
        # Need at least slow_window + 1 data points to calculate signals
        if len(self.historical_data[instrument]) <= self.slow_window:
            return
        
        # Calculate moving averages
        df = pd.DataFrame(self.historical_data[instrument])
        fast_ma = df['price'].rolling(window=self.fast_window).mean()
        slow_ma = df['price'].rolling(window=self.slow_window).mean()
        
        # Check for crossover
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return
        
        # Current values
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        
        # Previous values
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        
        # Detect crossover
        if prev_fast <= prev_slow and current_fast > current_slow:
            # Bullish crossover - fast crosses above slow
            signal_type = 'LONG'
            strength = 0.8  # Strong buy signal
            self.send_signal(instrument, signal_type, strength, {
                'fast_ma': current_fast,
                'slow_ma': current_slow,
                'price': price
            })
            self.last_signal[instrument] = signal_type
        
        elif prev_fast >= prev_slow and current_fast < current_slow:
            # Bearish crossover - fast crosses below slow
            signal_type = 'SHORT'
            strength = -0.8  # Strong sell signal
            self.send_signal(instrument, signal_type, strength, {
                'fast_ma': current_fast,
                'slow_ma': current_slow,
                'price': price
            })
            self.last_signal[instrument] = signal_type


class MovingAverageExecutionAgent(ExecutionAgent):
    """
    Agent that executes trades based on moving average crossover signals.
    """
    
    def __init__(self, agent_id: str, position_size: float = 100):
        super().__init__(agent_id)
        self.position_size = position_size
        self.positions = {}  # Instrument -> position (positive for long, negative for short)
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.positions = {}
    
    def on_signal(self, event) -> None:
        """Process trading signals and execute trades."""
        instrument = event.instrument
        signal_type = event.signal_type
        
        # Initialize position if needed
        if instrument not in self.positions:
            self.positions[instrument] = 0
        
        # Get current position
        current_position = self.positions[instrument]
        
        # Handle long signal
        if signal_type == 'LONG':
            if current_position < 0:
                # First, close short position
                self.send_order(
                    instrument=instrument,
                    quantity=abs(current_position),
                    side='BUY',  # Buy to close short
                    order_type='MARKET'
                )
                current_position = 0
            
            if current_position == 0:
                # Open long position
                self.send_order(
                    instrument=instrument,
                    quantity=self.position_size,
                    side='BUY',
                    order_type='MARKET'
                )
                current_position = self.position_size
        
        # Handle short signal
        elif signal_type == 'SHORT':
            if current_position > 0:
                # First, close long position
                self.send_order(
                    instrument=instrument,
                    quantity=current_position,
                    side='SELL',  # Sell to close long
                    order_type='MARKET'
                )
                current_position = 0
            
            if current_position == 0:
                # Open short position
                self.send_order(
                    instrument=instrument,
                    quantity=self.position_size,
                    side='SELL',
                    order_type='MARKET'
                )
                current_position = -self.position_size
        
        # Update position
        self.positions[instrument] = current_position
    
    def on_order_fill(self, order, fill_price, fill_quantity) -> None:
        """Update positions when orders are filled."""
        instrument = order.instrument
        
        # Initialize position if needed
        if instrument not in self.positions:
            self.positions[instrument] = 0
        
        # Update position based on the fill
        if order.side == OrderSide.BUY:
            self.positions[instrument] += fill_quantity
        else:  # SELL
            self.positions[instrument] -= fill_quantity


class MovingAveragePod(MultiAgentPod):
    """
    Trading pod that implements a moving average crossover strategy.
    """
    
    def __init__(self, pod_id: str, instruments: List[str], 
                fast_window: int = 10, slow_window: int = 30,
                position_size: float = 100):
        super().__init__(pod_id, instruments)
        
        # Create the signal agent
        self.signal_agent = MovingAverageSignalAgent(
            agent_id=f"{pod_id}_signal",
            fast_window=fast_window,
            slow_window=slow_window
        )
        
        # Create the execution agent
        self.execution_agent = MovingAverageExecutionAgent(
            agent_id=f"{pod_id}_execution",
            position_size=position_size
        )
        
        # Add agents to the pod
        self.add_agent(self.signal_agent.agent_id, self.signal_agent)
        self.add_agent(self.execution_agent.agent_id, self.execution_agent) 