import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

class UnifiedRateLimiter:
    """Centralized rate limiter for all API services."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # Service-specific rate limits (calls per second)
        self.service_limits = {
            'spotify': 0.2,       # 1 call per 5 seconds
            'musicbrainz': 0.25,  # 1 call per 4 seconds
            'openrouter': 2.0     # 2 calls per second (OpenRouter Gemini 2.5 Flash)
        }
        
        # Track last call times per service
        self.last_call_times: Dict[str, Optional[float]] = {
            service: None for service in self.service_limits
        }
        
        # Track consecutive calls for backoff
        self.consecutive_calls: Dict[str, int] = {
            service: 0 for service in self.service_limits
        }
        
        # Locks for thread safety per service
        self.service_locks = {
            service: threading.Lock() for service in self.service_limits
        }
    
    def wait_if_needed(self, service: str, enable_backoff: bool = True) -> None:
        """
        Wait if needed based on service rate limits.
        
        Args:
            service: Service name ('spotify', 'musicbrainz', 'openrouter')
            enable_backoff: Whether to apply exponential backoff for consecutive calls
        """
        if service not in self.service_limits:
            print(f"Warning: Unknown service '{service}' for rate limiting")
            return
        
        with self.service_locks[service]:
            current_time = time.time()
            calls_per_second = self.service_limits[service]
            required_gap = 1.0 / calls_per_second
            
            if self.last_call_times[service] is not None:
                elapsed = current_time - self.last_call_times[service]
                
                if elapsed < required_gap:
                    sleep_time = required_gap - elapsed
                    
                    # Apply backoff for consecutive calls
                    if enable_backoff and self.consecutive_calls[service] > 5:
                        backoff_multiplier = min(self.consecutive_calls[service] * 0.1, 2.0)
                        sleep_time *= (1 + backoff_multiplier)
                        print(f"Applying backoff for {service}: {sleep_time:.2f}s")
                    
                    print(f"Rate limiting {service}: waiting {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    
                    # Reset consecutive calls after backoff
                    if enable_backoff and sleep_time > required_gap * 1.5:
                        self.consecutive_calls[service] = 0
                else:
                    # Reset consecutive calls if enough time has passed
                    if elapsed > required_gap * 2:
                        self.consecutive_calls[service] = 0
            
            # Update tracking
            self.last_call_times[service] = time.time()
            self.consecutive_calls[service] += 1
    
    def reset_service(self, service: str) -> None:
        """Reset rate limiting state for a service."""
        if service in self.service_limits:
            with self.service_locks[service]:
                self.last_call_times[service] = None
                self.consecutive_calls[service] = 0
    
    def get_service_status(self, service: str) -> Dict:
        """Get current status for a service."""
        if service not in self.service_limits:
            return {}
        
        with self.service_locks[service]:
            last_call = self.last_call_times[service]
            return {
                'service': service,
                'calls_per_second': self.service_limits[service],
                'last_call': datetime.fromtimestamp(last_call) if last_call else None,
                'consecutive_calls': self.consecutive_calls[service],
                'time_since_last_call': time.time() - last_call if last_call else None
            }