import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

class UnifiedRateLimiter:
    """Centralized rate limiter for all API services.

    Threads acquire a scheduled slot, then sleep outside the lock
    so other threads can schedule their own slots concurrently.
    """

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

        # Service-specific rate limits (minimum seconds between calls)
        # MusicBrainz: 1 req/sec officially, we use 1.1s to be safe
        # Spotify: generous rate limits, 0.1s gap is plenty
        # OpenRouter: 2 calls/sec
        self.service_gaps = {
            'spotify': 0.1,
            'musicbrainz': 1.1,
            'openrouter': 0.5
        }

        # Next allowed call time per service
        self.next_allowed: Dict[str, float] = {
            service: 0.0 for service in self.service_gaps
        }

        # Track consecutive calls for backoff
        self.consecutive_calls: Dict[str, int] = {
            service: 0 for service in self.service_gaps
        }

        # Scheduling lock per service (held briefly, not during sleep)
        self.service_locks = {
            service: threading.Lock() for service in self.service_gaps
        }

    def wait_if_needed(self, service: str, enable_backoff: bool = True) -> None:
        """
        Wait if needed based on service rate limits.

        The lock is only held to compute and reserve a time slot.
        The actual sleep happens outside the lock so other threads
        can schedule their own slots in parallel.
        """
        if service not in self.service_gaps:
            print(f"Warning: Unknown service '{service}' for rate limiting")
            return

        gap = self.service_gaps[service]

        # Acquire lock briefly to reserve our slot
        with self.service_locks[service]:
            now = time.time()

            # Apply backoff for many consecutive calls
            effective_gap = gap
            if enable_backoff and self.consecutive_calls[service] > 10:
                backoff_multiplier = min(self.consecutive_calls[service] * 0.05, 1.0)
                effective_gap = gap * (1 + backoff_multiplier)

            # Our slot is the next allowed time
            my_slot = max(now, self.next_allowed[service])

            # Reserve slot: next caller must wait after us
            self.next_allowed[service] = my_slot + effective_gap
            self.consecutive_calls[service] += 1

            sleep_time = my_slot - now

        # Sleep OUTSIDE the lock — other threads can schedule while we wait
        if sleep_time > 0.01:
            time.sleep(sleep_time)

    def reset_service(self, service: str) -> None:
        """Reset rate limiting state for a service."""
        if service in self.service_gaps:
            with self.service_locks[service]:
                self.next_allowed[service] = 0.0
                self.consecutive_calls[service] = 0

    def get_service_status(self, service: str) -> Dict:
        """Get current status for a service."""
        if service not in self.service_gaps:
            return {}

        with self.service_locks[service]:
            next_at = self.next_allowed[service]
            now = time.time()
            return {
                'service': service,
                'min_gap_seconds': self.service_gaps[service],
                'next_allowed_in': max(0, next_at - now),
                'consecutive_calls': self.consecutive_calls[service],
            }
