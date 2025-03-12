import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal

import pandas as pd
import numpy as np
from pydantic import BaseModel, Field

from src.core.event import MarketDataEvent
from src.core.order import OrderSide, OrderType
from src.pods.agents.base_agent import SignalAgent, ExecutionAgent
from src.pods.base import MultiAgentPod


class CongressionalSignalData(BaseModel):
    """Data structure for congressional trading signals."""
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


class CongressionalSignalAgent(SignalAgent):
    """
    Agent that generates trading signals based on congressional trading patterns and policy insights.
    
    This agent analyzes:
    1. Companies likely to benefit from upcoming legislation and regulatory changes
    2. Government contractors and sectors with significant public sector exposure
    3. Sectors with active policy discussions and potential regulatory shifts
    4. Strategic long-term positions in market-leading companies
    """
    
    def __init__(self, agent_id: str, signal_threshold: float = 0.6):
        super().__init__(agent_id)
        self.signal_threshold = signal_threshold
        self.historical_data = {}  # Instrument -> DataFrame
        self.last_signal = {}  # Instrument -> last signal type
        self.analysis_cache = {}  # Instrument -> analysis results
        self.last_analysis_time = {}  # Instrument -> datetime of last analysis
        
        # Configuration for how often to re-analyze (to avoid doing it on every tick)
        self.analysis_interval = pd.Timedelta(days=7)  # Re-analyze weekly
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.historical_data = {}
        self.last_signal = {}
        self.analysis_cache = {}
        self.last_analysis_time = {}
    
    def on_market_data(self, event: MarketDataEvent) -> None:
        """Process market data and generate trading signals."""
        instrument = event.instrument
        
        # Initialize data structure if needed
        if instrument not in self.historical_data:
            self.historical_data[instrument] = []
            self.last_signal[instrument] = None
            self.last_analysis_time[instrument] = None
        
        # Extract price from the data
        price = event.data.get('close', event.data.get('price'))
        if price is None:
            return
        
        # Add to historical data
        self.historical_data[instrument].append({
            'timestamp': event.timestamp,
            'price': price
        })
        
        # Check if we need to perform analysis
        should_analyze = (
            self.last_analysis_time.get(instrument) is None or
            (event.timestamp - self.last_analysis_time[instrument]) > self.analysis_interval
        )
        
        if should_analyze:
            self.last_analysis_time[instrument] = event.timestamp
            self._analyze_and_signal(instrument, event.timestamp, price)
    
    def _analyze_and_signal(self, instrument: str, timestamp: datetime, current_price: float) -> None:
        """
        Perform congressional trading analysis and generate signals.
        
        In a real implementation, this would call external APIs or models to analyze:
        - Recent legislation and regulatory changes affecting the company
        - Government contract opportunities and public sector exposure
        - Policy trends and discussions relevant to the company's sector
        """
        # This is a simplified mock implementation
        # In a real system, this would retrieve actual congressional trading data
        # and perform sophisticated policy analysis
        
        # Simulate analysis results
        analysis = self._mock_congressional_analysis(instrument, timestamp)
        
        # Store in cache
        self.analysis_cache[instrument] = analysis
        
        # Convert analysis to signal
        if analysis['signal'] == "bullish" and analysis['confidence'] >= self.signal_threshold:
            signal_type = 'LONG'
            strength = min(analysis['confidence'], 1.0)  # Ensure strength is between 0 and 1
            
            # Only send signal if it's different from the last one
            if self.last_signal.get(instrument) != signal_type:
                self.send_signal(instrument, signal_type, strength, {
                    'reasoning': analysis['reasoning'],
                    'price': current_price
                })
                self.last_signal[instrument] = signal_type
                
        elif analysis['signal'] == "bearish" and analysis['confidence'] >= self.signal_threshold:
            signal_type = 'SHORT'
            strength = -min(analysis['confidence'], 1.0)  # Negative for short signals
            
            # Only send signal if it's different from the last one
            if self.last_signal.get(instrument) != signal_type:
                self.send_signal(instrument, signal_type, strength, {
                    'reasoning': analysis['reasoning'],
                    'price': current_price
                })
                self.last_signal[instrument] = signal_type
                
        elif self.last_signal.get(instrument) is not None:
            # If we had a position but now signal is neutral or below threshold, exit
            signal_type = 'EXIT'
            strength = 0.0
            
            self.send_signal(instrument, signal_type, strength, {
                'reasoning': f"Exiting position due to neutral/low confidence signal: {analysis['reasoning']}",
                'price': current_price
            })
            self.last_signal[instrument] = None
    
    def _mock_congressional_analysis(self, instrument: str, timestamp: datetime) -> Dict[str, Any]:
        """
        Mock implementation for congressional trading analysis.
        
        In a real system, this would use actual data from APIs or ML models.
        """
        # This is just for demonstration - in a real system these would be actual results
        
        # Generate pseudo-random but consistent results for each instrument
        import hashlib
        seed = int(hashlib.md5(f"{instrument}:{timestamp.strftime('%Y-%m-%d')}".encode()).hexdigest(), 16) % 10000
        np.random.seed(seed)
        
        signals = ["bullish", "bearish", "neutral"]
        signal = np.random.choice(signals, p=[0.4, 0.4, 0.2])
        confidence = np.random.uniform(0.5, 0.95)
        
        # Generate mock reasoning
        reasons = {
            "bullish": [
                f"Recent legislation likely to benefit {instrument}'s sector",
                f"Increased government spending in {instrument}'s market",
                f"Favorable regulatory changes expected for {instrument}",
                f"Multiple congressional insiders recently purchased {instrument}"
            ],
            "bearish": [
                f"Potential regulatory challenges facing {instrument}",
                f"Decreased government spending expected in {instrument}'s sector",
                f"Unfavorable policy changes on the horizon for {instrument}",
                f"Multiple congressional insiders recently sold {instrument}"
            ],
            "neutral": [
                f"Mixed policy signals for {instrument}'s sector",
                f"No significant congressional trading activity in {instrument}",
                f"Balanced regulatory outlook for {instrument}",
                f"Unclear legislative impact on {instrument}'s business"
            ]
        }
        
        reason_idx = seed % len(reasons[signal])
        reasoning = reasons[signal][reason_idx]
        
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning
        }


class CongressionalExecutionAgent(ExecutionAgent):
    """
    Agent that executes trades based on congressional trading signals.
    """
    
    def __init__(self, agent_id: str, position_size: float = 100, max_positions: int = 5):
        super().__init__(agent_id)
        self.position_size = position_size
        self.max_positions = max_positions
        self.positions = {}  # Instrument -> position (positive for long, negative for short)
        self.active_instruments = set()  # Set of instruments with active positions
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.positions = {}
        self.active_instruments = set()
    
    def on_signal(self, event) -> None:
        """Process trading signals and execute trades."""
        instrument = event.instrument
        signal_type = event.signal_type
        
        # Initialize position if needed
        if instrument not in self.positions:
            self.positions[instrument] = 0
        
        # Get current position
        current_position = self.positions[instrument]
        
        # Skip if we already have max positions and this is a new position request
        if (len(self.active_instruments) >= self.max_positions and 
            instrument not in self.active_instruments and
            signal_type in ['LONG', 'SHORT']):
            return
        
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
                self.positions[instrument] = 0
                current_position = 0
            
            if current_position == 0:
                # Open long position
                order_quantity = self.calculate_position_size(instrument, event.strength)
                self.send_order(
                    instrument=instrument,
                    quantity=order_quantity,
                    side='BUY',
                    order_type='MARKET'
                )
                self.positions[instrument] = order_quantity
                self.active_instruments.add(instrument)
        
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
                self.positions[instrument] = 0
                current_position = 0
            
            if current_position == 0:
                # Open short position
                order_quantity = self.calculate_position_size(instrument, abs(event.strength))
                self.send_order(
                    instrument=instrument,
                    quantity=order_quantity,
                    side='SELL',
                    order_type='MARKET'
                )
                self.positions[instrument] = -order_quantity
                self.active_instruments.add(instrument)
        
        # Handle exit signal
        elif signal_type == 'EXIT':
            if current_position > 0:
                # Close long position
                self.send_order(
                    instrument=instrument,
                    quantity=current_position,
                    side='SELL',
                    order_type='MARKET'
                )
                self.positions[instrument] = 0
                self.active_instruments.discard(instrument)
            
            elif current_position < 0:
                # Close short position
                self.send_order(
                    instrument=instrument,
                    quantity=abs(current_position),
                    side='BUY',
                    order_type='MARKET'
                )
                self.positions[instrument] = 0
                self.active_instruments.discard(instrument)
    
    def calculate_position_size(self, instrument: str, signal_strength: float) -> float:
        """
        Calculate the position size based on signal strength.
        
        Parameters:
        - instrument: The instrument to trade
        - signal_strength: The strength of the signal (0.0 to 1.0)
        
        Returns the quantity to trade.
        """
        # Scale position size by signal strength
        # Strong signals get full position size, weak signals get less
        scaled_size = self.position_size * signal_strength
        
        # Ensure minimum position size
        return max(scaled_size, self.position_size * 0.25)
    
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
        
        # Update active instruments set
        if self.positions[instrument] != 0:
            self.active_instruments.add(instrument)
        else:
            self.active_instruments.discard(instrument)


class CongressionalTradingPod(MultiAgentPod):
    """
    Trading pod that implements a congressional trading strategy.
    
    Analyzes stocks using congressional trading patterns and policy insights:
    1. Companies likely to benefit from upcoming legislation and regulatory changes
    2. Government contractors and sectors with significant public sector exposure
    3. Sectors with active policy discussions and potential regulatory shifts
    4. Strategic long-term positions in market-leading companies
    """
    
    def __init__(
        self,
        pod_id: str,
        instruments: List[str],
        signal_threshold: float = 0.6,
        position_size: float = 100,
        max_positions: int = 5
    ):
        super().__init__(pod_id, instruments)
        
        # Create the signal agent
        self.signal_agent = CongressionalSignalAgent(
            agent_id=f"{pod_id}_signal",
            signal_threshold=signal_threshold
        )
        
        # Create the execution agent
        self.execution_agent = CongressionalExecutionAgent(
            agent_id=f"{pod_id}_execution",
            position_size=position_size,
            max_positions=max_positions
        )
        
        # Add agents to the pod
        self.add_agent(self.signal_agent.agent_id, self.signal_agent)
        self.add_agent(self.execution_agent.agent_id, self.execution_agent) 