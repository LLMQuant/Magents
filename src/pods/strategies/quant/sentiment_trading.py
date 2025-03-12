import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from src.core.event import MarketDataEvent
from src.core.order import OrderSide, OrderType
from src.pods.agents.base_agent import SignalAgent, ExecutionAgent
from src.pods.base import MultiAgentPod


class SentimentSignalAgent(SignalAgent):
    """
    Agent that generates trading signals based on market sentiment analysis.
    
    It analyzes:
    1. Insider trading patterns
    2. News sentiment
    3. Social media sentiment (if available)
    """
    
    def __init__(self, agent_id: str, signal_threshold: float = 0.6):
        super().__init__(agent_id)
        self.signal_threshold = signal_threshold
        self.historical_data = {}  # Instrument -> DataFrame
        self.sentiment_data = {}  # Instrument -> Dict of sentiment metrics
        self.last_signal = {}  # Instrument -> last signal type
        self.analysis_cache = {}  # Instrument -> analysis results
        self.last_analysis_time = {}  # Instrument -> datetime of last analysis
        
        # Configuration for how often to re-analyze (to avoid doing it on every tick)
        self.analysis_interval = pd.Timedelta(days=1)  # Re-analyze daily
    
    def initialize(self, start_date: datetime) -> None:
        """Initialize agent state."""
        self.historical_data = {}
        self.sentiment_data = {}
        self.last_signal = {}
        self.analysis_cache = {}
        self.last_analysis_time = {}
    
    def on_market_data(self, event: MarketDataEvent) -> None:
        """Process market data and generate trading signals."""
        instrument = event.instrument
        
        # Initialize data structure if needed
        if instrument not in self.historical_data:
            self.historical_data[instrument] = []
            self.sentiment_data[instrument] = {
                'insider_trades': [],
                'news_sentiment': [],
                'social_sentiment': []
            }
            self.last_signal[instrument] = None
            self.last_analysis_time[instrument] = None
        
        # Extract price and sentiment data from the event
        price = event.data.get('close', event.data.get('price'))
        if price is None:
            return
        
        # Add to historical data
        self.historical_data[instrument].append({
            'timestamp': event.timestamp,
            'price': price
        })
        
        # Extract sentiment data if available in event
        # In a real system, this would be provided by a sentiment data feed
        for key in ['insider_trades', 'news_sentiment', 'social_sentiment']:
            if key in event.data:
                self.sentiment_data[instrument][key].append({
                    'timestamp': event.timestamp,
                    'data': event.data[key]
                })
        
        # Check if we need to perform analysis
        should_analyze = (
            self.last_analysis_time.get(instrument) is None or
            (event.timestamp - self.last_analysis_time[instrument]) > self.analysis_interval
        )
        
        if should_analyze and len(self.historical_data[instrument]) >= 5:  # Need some history
            self.last_analysis_time[instrument] = event.timestamp
            self._analyze_and_signal(instrument, event.timestamp, price)
    
    def _analyze_and_signal(self, instrument: str, timestamp: datetime, current_price: float) -> None:
        """
        Perform sentiment analysis and generate signals.
        """
        # Get historical prices as DataFrame for calculation
        price_df = pd.DataFrame(self.historical_data[instrument])
        
        # Perform sentiment analysis
        analysis = self._sentiment_analysis(instrument, price_df, current_price)
        
        # Store in cache
        self.analysis_cache[instrument] = analysis
        
        # Determine signal based on analysis
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
    
    def _sentiment_analysis(self, instrument: str, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Perform sentiment analysis based on:
        1. Insider trading patterns
        2. News sentiment
        3. Social media sentiment
        """
        # In a real implementation, we'd use actual sentiment data
        # Here we'll use a simple mock implementation
        
        score = 0
        max_score = 10
        details = []
        
        # 1. Analyze insider trading if available
        insider_trades = self.sentiment_data[instrument]['insider_trades']
        if insider_trades:
            # Get the most recent insider trades (up to 10)
            recent_trades = insider_trades[-10:]
            
            # Calculate if there are more buys than sells
            buys = sum(1 for trade in recent_trades if trade.get('data', {}).get('type') == 'buy')
            sells = sum(1 for trade in recent_trades if trade.get('data', {}).get('type') == 'sell')
            
            if buys > sells:
                score += 3
                details.append(f"Insiders buying more than selling ({buys} buys vs {sells} sells)")
            elif sells > buys:
                details.append(f"Insiders selling more than buying ({sells} sells vs {buys} buys)")
        
        # 2. Analyze news sentiment if available
        news_items = self.sentiment_data[instrument]['news_sentiment']
        if news_items:
            # Get the most recent news items (up to 20)
            recent_news = news_items[-20:]
            
            # Calculate average sentiment (-1 to 1 scale)
            sentiments = [item.get('data', {}).get('sentiment', 0) for item in recent_news]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
            
            if avg_sentiment > 0.3:
                score += 4
                details.append(f"Positive news sentiment: {avg_sentiment:.2f}")
            elif avg_sentiment < -0.3:
                details.append(f"Negative news sentiment: {avg_sentiment:.2f}")
            else:
                score += 1
                details.append(f"Neutral news sentiment: {avg_sentiment:.2f}")
        
        # 3. Analyze social media sentiment if available
        social_items = self.sentiment_data[instrument]['social_sentiment']
        if social_items:
            # Get the most recent social posts (up to 50)
            recent_social = social_items[-50:]
            
            # Calculate average sentiment (-1 to 1 scale)
            sentiments = [item.get('data', {}).get('sentiment', 0) for item in recent_social]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
            
            if avg_sentiment > 0.2:
                score += 3
                details.append(f"Positive social sentiment: {avg_sentiment:.2f}")
            elif avg_sentiment < -0.2:
                details.append(f"Negative social sentiment: {avg_sentiment:.2f}")
            else:
                score += 1
                details.append(f"Neutral social sentiment: {avg_sentiment:.2f}")
        
        # If there's no sentiment data, use mock data for demo purposes
        if not insider_trades and not news_items and not social_items:
            # Use stochastic model based on price changes for demo
            if len(df) >= 5:
                price_changes = df['price'].pct_change().dropna().tail(5)
                if price_changes.mean() > 0:
                    score += 4
                    details.append(f"Simulated positive sentiment based on recent price action")
                else:
                    details.append(f"Simulated negative sentiment based on recent price action")
        
        # Convert score to confidence
        confidence = score / max_score
        
        # Determine signal
        if confidence >= 0.6:
            signal = "bullish"
        elif confidence <= 0.3:
            signal = "bearish"
        else:
            signal = "neutral"
            
        reasoning = "; ".join(details) if details else "Insufficient sentiment data for analysis"
            
        return {
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "score": score,
            "max_score": max_score
        }


class SentimentExecutionAgent(ExecutionAgent):
    """
    Agent that executes trades based on sentiment signals.
    
    It focuses on:
    1. Quick entry for strong signals
    2. Pyramiding into positions
    3. Dynamic position sizing based on signal strength
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
            
            if current_position == 0 or current_position * 2 <= self.position_size:
                # Open new or add to long position (pyramiding)
                order_quantity = self.calculate_position_size(instrument, event.strength)
                self.send_order(
                    instrument=instrument,
                    quantity=order_quantity,
                    side='BUY',
                    order_type='MARKET'
                )
                self.positions[instrument] = current_position + order_quantity
                self.active_instruments.add(instrument)
                
                # Update entry price (weighted average if pyramiding)
                if current_position == 0:
                    self.entry_prices[instrument] = event.metadata.get('price', 0)
                else:
                    current_value = current_position * self.entry_prices[instrument]
                    new_value = order_quantity * event.metadata.get('price', 0)
                    self.entry_prices[instrument] = (current_value + new_value) / (current_position + order_quantity)
        
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
            
            if current_position == 0 or abs(current_position) * 2 <= self.position_size:
                # Open new or add to short position (pyramiding)
                order_quantity = self.calculate_position_size(instrument, abs(event.strength))
                self.send_order(
                    instrument=instrument,
                    quantity=order_quantity,
                    side='SELL',
                    order_type='MARKET'
                )
                self.positions[instrument] = current_position - order_quantity  # Negative for short
                self.active_instruments.add(instrument)
                
                # Update entry price (weighted average if pyramiding)
                if current_position == 0:
                    self.entry_prices[instrument] = event.metadata.get('price', 0)
                else:
                    current_value = abs(current_position) * self.entry_prices[instrument]
                    new_value = order_quantity * event.metadata.get('price', 0)
                    self.entry_prices[instrument] = (current_value + new_value) / (abs(current_position) + order_quantity)
        
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
    
    def calculate_position_size(self, instrument: str, signal_strength: float) -> float:
        """
        Calculate the position size based on sentiment signal strength.
        
        Parameters:
        - instrument: The instrument to trade
        - signal_strength: The strength of the signal (0.0 to 1.0)
        
        Returns the quantity to trade.
        """
        # Base position size
        base_size = self.position_size / 2
        
        # Adjust for signal strength - stronger signals get larger positions
        adjusted_size = base_size * (1 + signal_strength)
        
        # Ensure minimum position size
        return max(adjusted_size, base_size * 0.5)
    
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


class SentimentTradingPod(MultiAgentPod):
    """
    Trading pod that implements a market sentiment-based strategy.
    
    Analyzes market sentiment through:
    1. Insider trading patterns
    2. News sentiment analysis
    3. Social media sentiment analysis (if available)
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
        self.signal_agent = SentimentSignalAgent(
            agent_id=f"{pod_id}_signal",
            signal_threshold=signal_threshold
        )
        
        # Create the execution agent
        self.execution_agent = SentimentExecutionAgent(
            agent_id=f"{pod_id}_execution",
            position_size=position_size,
            max_positions=max_positions
        )
        
        # Add agents to the pod
        self.add_agent(self.signal_agent.agent_id, self.signal_agent)
        self.add_agent(self.execution_agent.agent_id, self.execution_agent) 