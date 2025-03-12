import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Union

import pandas as pd
import numpy as np

from src.core.event import EventType, RiskEvent
from src.core.order import Order, OrderSide
from src.core.portfolio import Portfolio
from src.risk.limits import RiskLimit


class RiskManager:
    """
    Central risk management system that enforces risk constraints
    and monitors portfolio risk metrics.
    """
    
    def __init__(self):
        self.risk_limits: Dict[str, List[RiskLimit]] = {}  # Pod-specific limits
        self.global_limits: List[RiskLimit] = []  # Global limits
        self.pod_status: Dict[str, str] = {}  # Status of each pod (e.g., 'ACTIVE', 'HALTED')
        self.drawdown_history: Dict[str, List[float]] = {}  # Drawdown history by pod
        self.risk_events = []  # List of past risk events
        self.logger = logging.getLogger(__name__)
    
    def add_pod_limit(self, pod_id: str, limit: RiskLimit) -> None:
        """Add a risk limit for a specific pod."""
        if pod_id not in self.risk_limits:
            self.risk_limits[pod_id] = []
        
        self.risk_limits[pod_id].append(limit)
        self.logger.info(f"Added {limit.limit_type} limit for pod {pod_id}")
    
    def add_global_limit(self, limit: RiskLimit) -> None:
        """Add a global risk limit (applies to all pods)."""
        self.global_limits.append(limit)
        self.logger.info(f"Added global {limit.limit_type} limit")
    
    def validate_order(self, order: Order, portfolio: Portfolio) -> bool:
        """
        Validate an order against risk constraints.
        Returns True if the order is allowed, False otherwise.
        """
        pod_id = order.pod_id
        
        # Check if the pod is active
        if pod_id in self.pod_status and self.pod_status[pod_id] != 'ACTIVE':
            self.logger.warning(f"Order from pod {pod_id} rejected: pod is {self.pod_status[pod_id]}")
            return False
        
        # Apply pod-specific limits
        if pod_id in self.risk_limits:
            for limit in self.risk_limits[pod_id]:
                if not limit.validate_order(order, portfolio):
                    self.logger.warning(f"Order from pod {pod_id} rejected: {limit.limit_type} limit")
                    return False
        
        # Apply global limits
        for limit in self.global_limits:
            if not limit.validate_order(order, portfolio):
                self.logger.warning(f"Order from pod {pod_id} rejected: global {limit.limit_type} limit")
                return False
        
        return True
    
    def monitor_portfolio(self, pod_id: str, portfolio: Portfolio, event_queue=None) -> List[RiskEvent]:
        """
        Monitor a pod's portfolio for risk limit breaches.
        Returns a list of RiskEvent objects for any breaches.
        """
        events = []
        
        # Update drawdown history
        self._update_drawdown(pod_id, portfolio)
        
        # Check pod-specific limits
        if pod_id in self.risk_limits:
            for limit in self.risk_limits[pod_id]:
                if not limit.validate_portfolio(portfolio):
                    # Create a risk event
                    event = self._create_risk_event(pod_id, limit.limit_type, limit.breach_details(portfolio))
                    events.append(event)
                    
                    # Log the event
                    self.logger.warning(f"Risk limit breach for pod {pod_id}: {limit.limit_type}")
                    
                    # Take action based on severity
                    if limit.severity == 'CRITICAL':
                        self.pod_status[pod_id] = 'HALTED'
                        self.logger.warning(f"Pod {pod_id} halted due to critical risk breach")
        
        # Check global limits (only relevant for portfolio-level limits)
        for limit in self.global_limits:
            if not limit.validate_portfolio(portfolio):
                # Create a risk event
                event = self._create_risk_event(pod_id, limit.limit_type, limit.breach_details(portfolio))
                events.append(event)
                
                # Log the event
                self.logger.warning(f"Global risk limit breach for pod {pod_id}: {limit.limit_type}")
        
        # If there are risk events and an event queue, add them to the queue
        if events and event_queue:
            for event in events:
                event_queue.put(event)
        
        # Store events
        self.risk_events.extend(events)
        
        return events
    
    def monitor_all_portfolios(self, portfolios: Dict[str, Portfolio], event_queue=None) -> List[RiskEvent]:
        """Monitor all portfolios for risk limit breaches."""
        all_events = []
        
        # First, monitor individual portfolios
        for pod_id, portfolio in portfolios.items():
            events = self.monitor_portfolio(pod_id, portfolio, event_queue)
            all_events.extend(events)
        
        # TODO: Add checks for cross-portfolio limits (e.g., correlations)
        
        return all_events
    
    def get_pod_status(self, pod_id: str) -> str:
        """Get the status of a pod."""
        return self.pod_status.get(pod_id, 'ACTIVE')
    
    def set_pod_status(self, pod_id: str, status: str) -> None:
        """Set the status of a pod."""
        self.pod_status[pod_id] = status
        self.logger.info(f"Pod {pod_id} status set to {status}")
    
    def reset_pod_status(self, pod_id: str) -> None:
        """Reset a pod's status to ACTIVE."""
        self.pod_status[pod_id] = 'ACTIVE'
        self.logger.info(f"Pod {pod_id} status reset to ACTIVE")
    
    def get_max_drawdown(self, pod_id: str) -> float:
        """Get the maximum drawdown for a pod."""
        if pod_id in self.drawdown_history and self.drawdown_history[pod_id]:
            return min(self.drawdown_history[pod_id])
        return 0.0
    
    def get_current_drawdown(self, pod_id: str) -> float:
        """Get the current drawdown for a pod."""
        if pod_id in self.drawdown_history and self.drawdown_history[pod_id]:
            return self.drawdown_history[pod_id][-1]
        return 0.0
    
    def get_risk_metrics(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate various risk metrics for a portfolio."""
        # This is a basic implementation that can be extended
        metrics = {}
        
        # Get positions summary
        positions = portfolio.get_positions_summary()
        if positions.empty:
            return metrics
        
        # Calculate gross exposure
        metrics['gross_exposure'] = positions['market_value'].abs().sum()
        
        # Calculate net exposure
        metrics['net_exposure'] = positions['market_value'].sum()
        
        # Calculate long exposure
        long_positions = positions[positions['quantity'] > 0]
        metrics['long_exposure'] = long_positions['market_value'].sum() if not long_positions.empty else 0.0
        
        # Calculate short exposure
        short_positions = positions[positions['quantity'] < 0]
        metrics['short_exposure'] = short_positions['market_value'].abs().sum() if not short_positions.empty else 0.0
        
        # Calculate exposures relative to portfolio value
        portfolio_value = portfolio.total_value()
        if portfolio_value > 0:
            metrics['gross_exposure_pct'] = metrics['gross_exposure'] / portfolio_value * 100
            metrics['net_exposure_pct'] = metrics['net_exposure'] / portfolio_value * 100
            metrics['long_exposure_pct'] = metrics['long_exposure'] / portfolio_value * 100
            metrics['short_exposure_pct'] = metrics['short_exposure'] / portfolio_value * 100
        
        # Calculate concentration - largest position as % of portfolio
        if not positions.empty:
            max_position = positions['market_value'].abs().max()
            metrics['max_position_pct'] = max_position / portfolio_value * 100 if portfolio_value > 0 else 0.0
        
        return metrics
    
    def _update_drawdown(self, pod_id: str, portfolio: Portfolio) -> None:
        """Update the drawdown history for a pod."""
        if pod_id not in self.drawdown_history:
            self.drawdown_history[pod_id] = []
            
            # Initialize with the starting cash
            self.drawdown_history[pod_id].append(0.0)
            return
        
        # Calculate current drawdown
        starting_value = portfolio.starting_cash
        current_value = portfolio.total_value()
        
        if starting_value > 0:
            # Calculate drawdown as a percentage of the starting value
            current_drawdown = (current_value / starting_value - 1) * 100
            
            # If we're in a drawdown (negative return), it's a negative number
            # If we're up (positive return), drawdown is 0
            current_drawdown = min(0, current_drawdown)
        else:
            current_drawdown = 0.0
        
        self.drawdown_history[pod_id].append(current_drawdown)
    
    def _create_risk_event(self, pod_id: str, alert_type: str, details: Dict) -> RiskEvent:
        """Create a RiskEvent object."""
        # Determine severity based on the alert type
        if alert_type in ['DRAWDOWN_LIMIT', 'POSITION_LIMIT', 'LEVERAGE_LIMIT']:
            severity = 'CRITICAL'
        else:
            severity = 'WARNING'
        
        return RiskEvent(
            type=EventType.RISK,
            timestamp=datetime.now(),
            source="risk_manager",
            alert_type=alert_type,
            severity=severity,
            details=details,
            pod_id=pod_id
        ) 