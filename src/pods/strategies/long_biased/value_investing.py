import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import pandas as pd
import numpy as np
from dataclasses import dataclass

from src.core.event import MarketDataEvent
from src.core.order import OrderSide, OrderType
from src.pods.agents.base_agent import SignalAgent, ExecutionAgent
from src.pods.base import MultiAgentPod


class GrahamSignalAgent(SignalAgent):
    """
    Agent that generates trading signals based on Benjamin Graham's value investing principles.
    
    This agent analyzes:
    1. Earnings stability over multiple years
    2. Solid financial strength (low debt, adequate liquidity)
    3. Discount to intrinsic value (Graham Number, Net Current Asset Value)
    4. Adequate margin of safety
    """
    
    def __init__(self, agent_id: str, signal_threshold: float = 0.6):
        super().__init__(agent_id)
        self.signal_threshold = signal_threshold
        self.historical_data = {}  # Instrument -> DataFrame of historical prices/data
        self.financials = {}  # Instrument -> Dict of financial data
        self.last_signal = {}  # Instrument -> last signal type
        self.analysis_cache = {}  # Instrument -> analysis results
        self.last_analysis_time = {}  # Instrument -> datetime of last analysis
        
        # Configuration for how often to re-analyze (to avoid doing it on every tick)
        self.analysis_interval = pd.Timedelta(days=30)  # Re-analyze monthly
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.historical_data = {}
        self.financials = {}
        self.last_signal = {}
        self.analysis_cache = {}
        self.last_analysis_time = {}
    
    def on_market_data(self, event: MarketDataEvent) -> None:
        """Process market data and generate trading signals."""
        instrument = event.instrument
        
        # Initialize data structure if needed
        if instrument not in self.historical_data:
            self.historical_data[instrument] = []
            self.financials[instrument] = {}
            self.last_signal[instrument] = None
            self.last_analysis_time[instrument] = None
        
        # Extract price and other financial metrics from the data
        price = event.data.get('close', event.data.get('price'))
        if price is None:
            return
        
        # Add to historical data
        self.historical_data[instrument].append({
            'timestamp': event.timestamp,
            'price': price
        })
        
        # Extract financial metrics if available
        for key in ['eps', 'book_value', 'current_assets', 'total_liabilities', 
                   'current_ratio', 'debt_to_equity', 'dividend_yield']:
            if key in event.data:
                self.financials[instrument][key] = event.data[key]
        
        # Check if we need to perform analysis
        should_analyze = (
            self.last_analysis_time.get(instrument) is None or
            (event.timestamp - self.last_analysis_time[instrument]) > self.analysis_interval
        )
        
        if should_analyze and len(self.historical_data[instrument]) >= 10:  # Need some history
            self.last_analysis_time[instrument] = event.timestamp
            self._analyze_and_signal(instrument, event.timestamp, price)
    
    def _analyze_and_signal(self, instrument: str, timestamp: datetime, current_price: float) -> None:
        """
        Perform Graham-based value analysis and generate signals.
        """
        # Get historical prices as DataFrame for calculation
        df = pd.DataFrame(self.historical_data[instrument])
        
        # Perform Ben Graham's value analysis
        analysis = self._value_analysis(instrument, df, current_price)
        
        # Store in cache
        self.analysis_cache[instrument] = analysis
        
        # Determine signal based on analysis - bullish if good value, bearish if overvalued
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
    
    def _value_analysis(self, instrument: str, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Perform Benjamin Graham's value investing analysis.
        
        1. Earnings stability
        2. Financial strength
        3. Valuation (Graham Number, Net Current Asset Value)
        4. Margin of safety
        """
        # In a real implementation, this would use actual financial data
        # Here we'll use a simplified approach based on available data
        
        score = 0
        max_score = 10
        details = []
        
        # 1. Earnings stability (use EPS if available)
        eps = self.financials[instrument].get('eps')
        if eps is not None and eps > 0:
            score += 2
            details.append(f"Positive EPS of {eps:.2f}")
        elif eps is not None:
            details.append(f"Negative EPS of {eps:.2f}")
        
        # 2. Financial strength
        current_ratio = self.financials[instrument].get('current_ratio')
        debt_to_equity = self.financials[instrument].get('debt_to_equity')
        
        if current_ratio is not None and current_ratio >= 2.0:
            score += 2
            details.append(f"Strong current ratio of {current_ratio:.2f}")
        elif current_ratio is not None:
            details.append(f"Weak current ratio of {current_ratio:.2f}")
            
        if debt_to_equity is not None and debt_to_equity < 0.5:
            score += 2
            details.append(f"Low debt-to-equity ratio of {debt_to_equity:.2f}")
        elif debt_to_equity is not None:
            details.append(f"High debt-to-equity ratio of {debt_to_equity:.2f}")
        
        # 3. Valuation (Graham Number)
        # Graham Number = sqrt(22.5 * EPS * Book Value per Share)
        book_value = self.financials[instrument].get('book_value')
        if eps is not None and book_value is not None and eps > 0 and book_value > 0:
            graham_number = (22.5 * eps * book_value) ** 0.5
            
            if current_price < graham_number:
                margin_of_safety = (graham_number - current_price) / graham_number
                score += int(margin_of_safety * 6)  # Up to 3 points for good margin
                details.append(f"Price ({current_price:.2f}) below Graham Number ({graham_number:.2f}) with {margin_of_safety:.1%} margin of safety")
            else:
                details.append(f"Price ({current_price:.2f}) above Graham Number ({graham_number:.2f})")
        
        # Convert score to confidence
        confidence = score / max_score
        
        # Determine signal
        if confidence >= 0.7:
            signal = "bullish"
        elif confidence <= 0.3:
            signal = "bearish"
        else:
            signal = "neutral"
            
        reasoning = "; ".join(details)
            
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "score": score,
            "max_score": max_score
        }


class GrahamExecutionAgent(ExecutionAgent):
    """
    Agent that executes trades based on Ben Graham's value investing principles.
    
    This approach:
    1. Focuses on margin of safety for position sizing
    2. Uses a disciplined long-term approach
    3. Implements a diversified portfolio strategy
    """
    
    def __init__(self, agent_id: str, position_size: float = 100, max_positions: int = 5):
        super().__init__(agent_id)
        self.position_size = position_size
        self.max_positions = max_positions
        self.positions = {}  # Instrument -> position (positive for long, negative for short)
        self.active_instruments = set()  # Set of instruments with active positions
        self.entry_prices = {}  # Instrument -> entry price
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.positions = {}
        self.active_instruments = set()
        self.entry_prices = {}
    
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
        
        # Handle long signal - Graham style is predominantly long-only
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
                order_quantity = self.calculate_position_size(instrument, event.strength, event.metadata.get('price', 0))
                self.send_order(
                    instrument=instrument,
                    quantity=order_quantity,
                    side='BUY',
                    order_type='MARKET'
                )
                self.positions[instrument] = order_quantity
                self.active_instruments.add(instrument)
                self.entry_prices[instrument] = event.metadata.get('price', 0)
        
        # Handle bearish signal - Graham might not short but may exit overvalued positions
        elif signal_type == 'SHORT':
            # If we have a long position, close it (but don't go short)
            if current_position > 0:
                self.send_order(
                    instrument=instrument,
                    quantity=current_position,
                    side='SELL',  # Sell to close long
                    order_type='MARKET'
                )
                self.positions[instrument] = 0
                self.active_instruments.discard(instrument)
                self.entry_prices.pop(instrument, None)
        
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
                self.entry_prices.pop(instrument, None)
            
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
                self.entry_prices.pop(instrument, None)
    
    def calculate_position_size(self, instrument: str, signal_strength: float, price: float) -> float:
        """
        Calculate the position size based on Graham principles.
        
        Parameters:
        - instrument: The instrument to trade
        - signal_strength: The strength of the signal (0.0 to 1.0)
        - price: Current price for the instrument
        
        Returns the quantity to trade.
        """
        # Graham believed in allocation based on margin of safety
        # We'll use signal strength as a proxy for margin of safety
        
        # Base position size
        base_size = self.position_size
        
        # Adjust for signal strength (margin of safety)
        adjusted_size = base_size * signal_strength
        
        # Ensure minimum position size
        return max(adjusted_size, base_size * 0.25)
    
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
            # Update entry price if this is a new position
            if instrument not in self.entry_prices:
                self.entry_prices[instrument] = fill_price
        else:
            self.active_instruments.discard(instrument)
            self.entry_prices.pop(instrument, None)


class ValueInvestingPod(MultiAgentPod):
    """
    Trading pod that implements Benjamin Graham's value investing strategy.
    
    Analyzes stocks using Graham's principles:
    1. Earnings stability over multiple years
    2. Solid financial strength (low debt, adequate liquidity)
    3. Discount to intrinsic value (Graham Number, Net-Net)
    4. Adequate margin of safety
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
        self.signal_agent = GrahamSignalAgent(
            agent_id=f"{pod_id}_signal",
            signal_threshold=signal_threshold
        )
        
        # Create the execution agent
        self.execution_agent = GrahamExecutionAgent(
            agent_id=f"{pod_id}_execution",
            position_size=position_size,
            max_positions=max_positions
        )
        
        # Add agents to the pod
        self.add_agent(self.signal_agent.agent_id, self.signal_agent)
        self.add_agent(self.execution_agent.agent_id, self.execution_agent) 