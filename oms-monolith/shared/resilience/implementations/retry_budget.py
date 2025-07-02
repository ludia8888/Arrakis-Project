"""
Unified retry budget implementation
"""

import time
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Tuple

from ..interfaces import (
    RetryBudgetInterface,
    RetryBudgetConfig
)


class UnifiedRetryBudget(RetryBudgetInterface):
    """
    Retry budget implementation to prevent retry storms.
    
    Uses a sliding window to track the ratio of retries to total requests,
    ensuring retries don't exceed a configured percentage.
    """
    
    def __init__(self, config: Optional[RetryBudgetConfig] = None):
        self.config = config or RetryBudgetConfig()
        
        # Sliding window of (timestamp, is_retry) tuples
        self._window: Deque[Tuple[float, bool]] = deque()
        
        # Counters for current window
        self._total_in_window = 0
        self._retries_in_window = 0
        
        # Token bucket for rate limiting
        self._tokens = self.config.max_tokens
        self._last_refill = time.time()
        
        # Thread safety
        self._lock = threading.Lock()
    
    def can_retry(self) -> bool:
        """Check if retry is allowed within budget"""
        with self._lock:
            self._cleanup_window()
            
            # Check minimum requests threshold
            if self._total_in_window < self.config.min_requests:
                return True
            
            # Calculate current retry percentage
            if self._total_in_window == 0:
                current_percent = 0.0
            else:
                current_percent = (self._retries_in_window / self._total_in_window) * 100
            
            # Check if adding one more retry would exceed budget
            future_retries = self._retries_in_window + 1
            future_total = self._total_in_window + 1
            future_percent = (future_retries / future_total) * 100
            
            # Also check token bucket
            self._refill_tokens()
            has_tokens = self._tokens >= 1
            
            return future_percent <= self.config.budget_percent and has_tokens
    
    def record_attempt(self, is_retry: bool) -> None:
        """Record an attempt (original or retry)"""
        with self._lock:
            now = time.time()
            
            # Add to window
            self._window.append((now, is_retry))
            self._total_in_window += 1
            if is_retry:
                self._retries_in_window += 1
                # Consume token for retry
                self._tokens = max(0, self._tokens - 1)
            
            # Cleanup old entries
            self._cleanup_window()
    
    def get_remaining_budget_percent(self) -> float:
        """Get remaining retry budget as percentage"""
        with self._lock:
            self._cleanup_window()
            
            if self._total_in_window == 0:
                return self.config.budget_percent
            
            current_percent = (self._retries_in_window / self._total_in_window) * 100
            return max(0.0, self.config.budget_percent - current_percent)
    
    def reset(self) -> None:
        """Reset retry budget"""
        with self._lock:
            self._window.clear()
            self._total_in_window = 0
            self._retries_in_window = 0
            self._tokens = self.config.max_tokens
            self._last_refill = time.time()
    
    def get_metrics(self) -> dict:
        """Get retry budget metrics"""
        with self._lock:
            self._cleanup_window()
            
            if self._total_in_window == 0:
                retry_percent = 0.0
            else:
                retry_percent = (self._retries_in_window / self._total_in_window) * 100
            
            return {
                "total_requests": self._total_in_window,
                "retry_requests": self._retries_in_window,
                "retry_percent": retry_percent,
                "budget_percent": self.config.budget_percent,
                "remaining_budget_percent": self.get_remaining_budget_percent(),
                "tokens_available": self._tokens,
                "window_size_seconds": self.config.window_size.total_seconds()
            }
    
    def _cleanup_window(self) -> None:
        """Remove old entries from sliding window"""
        now = time.time()
        window_start = now - self.config.window_size.total_seconds()
        
        # Remove old entries
        while self._window and self._window[0][0] < window_start:
            timestamp, is_retry = self._window.popleft()
            self._total_in_window -= 1
            if is_retry:
                self._retries_in_window -= 1
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on configured rate"""
        now = time.time()
        elapsed = now - self._last_refill
        
        # Calculate tokens to add
        tokens_to_add = elapsed * self.config.tokens_per_second
        
        if tokens_to_add >= 1:
            self._tokens = min(
                self.config.max_tokens,
                self._tokens + int(tokens_to_add)
            )
            self._last_refill = now