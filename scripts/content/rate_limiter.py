"""Rate limiter for Gemini API calls, extracted from generate_summaries.py.

Note: this is NOT the same implementation as backend/gemini_tts_handler.py's
RateLimiter — the two have diverged (different window-tracking logic) and
that one is live production TTS code, not covered by this extraction.
"""
import time

from scripts.content.constants import APIConstants


class RateLimiter:
    """Rate limiter for API calls"""

    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        self.request_times = []
        self.token_counts = []

    def wait_if_needed(self, estimated_tokens: int = 0):
        """Wait if we're approaching rate limits"""
        current_time = time.time()

        # Remove requests older than 1 minute
        window = APIConstants.RATE_LIMIT_WINDOW_SECONDS
        self.request_times = [t for t in self.request_times if current_time - t < window]
        self.token_counts = [
            (t, count) for t, count in self.token_counts if current_time - t < window
        ]

        # Check request limit
        if len(self.request_times) >= self.max_requests:
            sleep_time = window - (current_time - self.request_times[0]) + 1
            print(f"Rate limit: Waiting {sleep_time:.1f}s for request quota...")
            time.sleep(sleep_time)
            self.request_times = []

        # Check token limit
        total_tokens = sum(count for _, count in self.token_counts)
        if total_tokens + estimated_tokens > self.max_tokens:
            if self.token_counts:
                sleep_time = window - (current_time - self.token_counts[0][0]) + 1
                print(f"Rate limit: Waiting {sleep_time:.1f}s for token quota...")
                time.sleep(sleep_time)
            self.token_counts = []

        # Record this request
        self.request_times.append(current_time)
        if estimated_tokens > 0:
            self.token_counts.append((current_time, estimated_tokens))
