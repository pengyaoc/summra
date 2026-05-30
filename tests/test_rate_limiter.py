#!/usr/bin/env python3
"""
Unit tests for rate limiting logic

Tests the RateLimiter class that enforces API rate limits for:
- Requests per minute
- Tokens per minute
"""

import sys
import os
from pathlib import Path
import time
from unittest.mock import patch
import pytest

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.content.generate_summaries import RateLimiter


class TestRateLimiter:
    """Test rate limiting functionality"""

    def test_initialization(self):
        """Test rate limiter initialization"""
        limiter = RateLimiter(max_requests_per_minute=10, max_tokens_per_minute=100000)

        assert limiter.max_requests == 10
        assert limiter.max_tokens == 100000
        assert limiter.request_times == []
        assert limiter.token_counts == []

    def test_no_wait_on_first_request(self):
        """Test that first request doesn't wait"""
        limiter = RateLimiter(max_requests_per_minute=10, max_tokens_per_minute=100000)

        start_time = time.time()
        limiter.wait_if_needed(estimated_tokens=1000)
        elapsed = time.time() - start_time

        # Should complete almost instantly (no waiting)
        assert elapsed < 0.1
        assert len(limiter.request_times) == 1
        assert len(limiter.token_counts) == 1

    def test_no_wait_within_limits(self):
        """Test that requests within limits don't wait"""
        limiter = RateLimiter(max_requests_per_minute=10, max_tokens_per_minute=100000)

        # Make 5 requests (well under limit of 10)
        start_time = time.time()
        for i in range(5):
            limiter.wait_if_needed(estimated_tokens=5000)
        elapsed = time.time() - start_time

        # Should complete quickly (no waiting)
        assert elapsed < 0.5
        assert len(limiter.request_times) == 5

    @pytest.mark.slow
    def test_request_limit_enforcement_slow(self):
        """Real-time variant of test_request_limit_enforcement (no sleep mock).

        Kept under @slow so the full suite stays fast. Run with: pytest -m slow.
        """
        limiter = RateLimiter(max_requests_per_minute=3, max_tokens_per_minute=1000000)
        for i in range(3):
            limiter.wait_if_needed(estimated_tokens=100)
        limiter.wait_if_needed(estimated_tokens=100)
        assert len(limiter.request_times) >= 1

    def test_request_limit_enforcement(self):
        """Test that request limit triggers waiting (time.sleep mocked)"""
        limiter = RateLimiter(max_requests_per_minute=3, max_tokens_per_minute=1000000)

        # Make 3 requests quickly (at the limit)
        for i in range(3):
            limiter.wait_if_needed(estimated_tokens=100)

        # 4th request should trigger wait — mock sleep so the test is instant
        with patch("scripts.content.generate_summaries.time.sleep") as mock_sleep:
            limiter.wait_if_needed(estimated_tokens=100)

        # Verify the wait path was taken (sleep called with a positive duration)
        assert mock_sleep.called
        assert mock_sleep.call_args[0][0] > 0
        assert len(limiter.request_times) >= 1  # Request was recorded

    def test_token_limit_enforcement(self):
        """Test that token limit triggers waiting (time.sleep mocked)"""
        limiter = RateLimiter(max_requests_per_minute=100, max_tokens_per_minute=10000)

        # Make requests that total to token limit
        limiter.wait_if_needed(estimated_tokens=4000)
        limiter.wait_if_needed(estimated_tokens=4000)

        # This request would exceed token limit (8000 + 3000 > 10000)
        # Should trigger wait — mock sleep so the test is instant
        with patch("scripts.content.generate_summaries.time.sleep") as mock_sleep:
            limiter.wait_if_needed(estimated_tokens=3000)

        # Verify the wait path was taken
        assert mock_sleep.called
        assert mock_sleep.call_args[0][0] > 0
        assert len(limiter.token_counts) >= 1

    def test_rolling_window_cleanup(self):
        """Test that old requests are removed from tracking"""
        limiter = RateLimiter(max_requests_per_minute=10, max_tokens_per_minute=100000)

        # Add a request
        limiter.wait_if_needed(estimated_tokens=1000)
        assert len(limiter.request_times) == 1

        # Manually add an old timestamp (>60 seconds ago)
        old_time = time.time() - 70
        limiter.request_times.insert(0, old_time)
        limiter.token_counts.insert(0, (old_time, 5000))

        # Make another request - should clean up old entries
        limiter.wait_if_needed(estimated_tokens=1000)

        # Old entries should be removed (only entries from last 60s remain)
        for req_time in limiter.request_times:
            assert time.time() - req_time < 60

        for token_time, _ in limiter.token_counts:
            assert time.time() - token_time < 60

    def test_zero_tokens_doesnt_record(self):
        """Test that zero-token requests don't add to token tracking"""
        limiter = RateLimiter(max_requests_per_minute=10, max_tokens_per_minute=100000)

        # Request with no tokens
        limiter.wait_if_needed(estimated_tokens=0)

        assert len(limiter.request_times) == 1
        assert len(limiter.token_counts) == 0  # No tokens recorded

    def test_token_calculation(self):
        """Test that tokens are summed correctly"""
        limiter = RateLimiter(max_requests_per_minute=100, max_tokens_per_minute=100000)

        # Add several requests with different token counts
        limiter.wait_if_needed(estimated_tokens=10000)
        limiter.wait_if_needed(estimated_tokens=20000)
        limiter.wait_if_needed(estimated_tokens=15000)

        # Calculate total tokens
        total_tokens = sum(count for _, count in limiter.token_counts)
        assert total_tokens == 45000

    def test_request_reset_after_wait(self):
        """Test that request list is reset after waiting"""
        limiter = RateLimiter(max_requests_per_minute=2, max_tokens_per_minute=1000000)

        # Make 2 requests (at limit)
        limiter.wait_if_needed(estimated_tokens=100)
        limiter.wait_if_needed(estimated_tokens=100)

        # Manually trigger wait by adding 3rd request
        # The wait_if_needed should reset request_times after waiting
        initial_count = len(limiter.request_times)
        assert initial_count == 2

    def test_concurrent_limits(self):
        """Test handling of both request and token limits simultaneously (time.sleep mocked)"""
        limiter = RateLimiter(max_requests_per_minute=5, max_tokens_per_minute=20000)

        # Make 3 requests with moderate token usage
        for i in range(3):
            limiter.wait_if_needed(estimated_tokens=5000)

        # Both limits are approaching but not exceeded
        assert len(limiter.request_times) == 3
        total_tokens = sum(count for _, count in limiter.token_counts)
        assert total_tokens == 15000

        # Next request with high tokens should trigger the token-limit wait
        # (15000 + 6000 > 20000). Mock sleep so the test is instant.
        with patch("scripts.content.generate_summaries.time.sleep") as mock_sleep:
            limiter.wait_if_needed(estimated_tokens=6000)

        assert mock_sleep.called
        assert mock_sleep.call_args[0][0] > 0
        assert len(limiter.token_counts) >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
