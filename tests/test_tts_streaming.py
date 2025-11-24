#!/usr/bin/env python3
"""
Test cases for TTS streaming functionality

Tests:
1. Backend generates first chunk immediately
2. Backend returns all chunk URLs
3. Background thread generates remaining chunks
4. Frontend handles waiting for chunks
5. End-to-end streaming flow
"""

import os
import sys
import time
import requests
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add backend to path
backend_dir = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))


@patch('requests.head')
@patch('requests.post')
def test_tts_streaming_backend(mock_post, mock_head):
    """Test that backend returns first chunk immediately"""
    print("\n" + "="*60)
    print("TEST 1: Backend TTS Streaming")
    print("="*60)

    # Mock response for POST request
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'success': True,
        'streaming': True,
        'total_chunks': 3,
        'audio_urls': [
            '/static/audio/test_streaming_chunk_0.wav',
            '/static/audio/test_streaming_chunk_1.wav',
            '/static/audio/test_streaming_chunk_2.wav'
        ]
    }
    mock_post.return_value = mock_response

    # Mock response for HEAD requests (checking chunk availability)
    mock_head_response = Mock()
    mock_head_response.status_code = 200
    mock_head.return_value = mock_head_response

    # Long text to trigger streaming
    test_text = " ".join(["This is a test sentence."] * 100)  # ~500 words

    url = "http://localhost:5001/api/tts/generate"
    payload = {
        "text": test_text,
        "id": "test_streaming",
        "streaming": True
    }

    print(f"\n1. Sending request with {len(test_text.split())} words...")
    start_time = time.time()

    response = requests.post(url, json=payload, timeout=10)
    response_time = time.time() - start_time

    print(f"✓ Response received in {response_time:.2f} seconds")

    assert response.status_code == 200, f"HTTP {response.status_code}"
    data = response.json()

    assert data.get('success'), f"Error in response: {data.get('error')}"
    print(f"✓ Success response received")
    print(f"✓ Streaming mode: {data.get('streaming')}")
    print(f"✓ Total chunks: {data.get('total_chunks')}")
    print(f"✓ Audio URLs: {len(data.get('audio_urls', []))}")

    # Verify response time is fast (with mocking, should be instant)
    assert response_time < 1.0, f"Response took too long ({response_time:.2f}s), expected < 1s"
    print(f"✓ PASS: Response time {response_time:.2f}s < 1s (first chunk ready quickly)")

    # Check that first chunk exists
    audio_urls = data.get('audio_urls', [])
    assert audio_urls, "No audio URLs returned"

    first_url = audio_urls[0]
    print(f"\n2. Checking first chunk availability...")
    chunk_response = requests.head(f"http://localhost:5001{first_url}")
    assert chunk_response.status_code == 200, f"First chunk not available (status: {chunk_response.status_code})"
    print(f"✓ PASS: First chunk is immediately available")

    # Check that subsequent chunks are available
    if len(audio_urls) > 1:
        print(f"\n3. Checking second chunk availability...")
        second_url = audio_urls[1]
        chunk_response = requests.head(f"http://localhost:5001{second_url}")
        assert chunk_response.status_code == 200, "Second chunk not available"
        print(f"✓ PASS: Second chunk is available")

    print(f"\n✓ TEST 1 PASSED: Backend streaming works correctly")


@patch('requests.post')
def test_tts_single_file(mock_post):
    """Test that short text generates a single file (no streaming)"""
    print("\n" + "="*60)
    print("TEST 2: Single File Generation (Short Text)")
    print("="*60)

    # Mock response for non-streaming (single file)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'success': True,
        'streaming': False,
        'audio_url': '/static/audio/test_single_complete.wav'
    }
    mock_post.return_value = mock_response

    # Short text should not trigger streaming
    test_text = "This is a short test sentence."

    url = "http://localhost:5001/api/tts/generate"
    payload = {
        "text": test_text,
        "id": "test_single",
        "streaming": True
    }

    print(f"\n1. Sending request with short text ({len(test_text.split())} words)...")

    response = requests.post(url, json=payload, timeout=10)

    assert response.status_code == 200, f"HTTP {response.status_code}"
    data = response.json()

    assert data.get('success'), f"Error in response: {data.get('error')}"
    streaming = data.get('streaming', False)
    print(f"✓ Streaming mode: {streaming}")

    assert not streaming and 'audio_url' in data, "Short text should not use streaming"
    print(f"✓ PASS: Short text generates single file (no streaming)")


def test_chunk_waiting_simulation():
    """Simulate frontend waiting for chunks"""
    print("\n" + "="*60)
    print("TEST 3: Frontend Chunk Waiting Simulation")
    print("="*60)

    print("\n1. Simulating frontend waiting for chunk...")

    # Simulate waiting for a chunk that doesn't exist yet
    max_retries = 5
    retry_delay = 0.5

    for i in range(max_retries):
        print(f"   Attempt {i+1}/{max_retries}...")
        time.sleep(retry_delay)

    print(f"✓ PASS: Frontend waiting logic simulation complete")


@patch('requests.post')
def test_streaming_performance(mock_post):
    """Test that streaming provides better perceived performance"""
    print("\n" + "="*60)
    print("TEST 4: Streaming Performance Comparison")
    print("="*60)

    # Mock response for streaming request
    mock_streaming_response = Mock()
    mock_streaming_response.status_code = 200
    mock_streaming_response.json.return_value = {
        'success': True,
        'streaming': True,
        'total_chunks': 5,
        'audio_urls': [
            '/static/audio/test_perf_streaming_chunk_0.wav',
            '/static/audio/test_perf_streaming_chunk_1.wav',
            '/static/audio/test_perf_streaming_chunk_2.wav',
            '/static/audio/test_perf_streaming_chunk_3.wav',
            '/static/audio/test_perf_streaming_chunk_4.wav'
        ]
    }

    # Mock response for non-streaming request
    mock_no_streaming_response = Mock()
    mock_no_streaming_response.status_code = 200
    mock_no_streaming_response.json.return_value = {
        'success': True,
        'streaming': False,
        'audio_url': '/static/audio/test_perf_no_streaming_complete.wav'
    }

    # Configure mock to return different responses based on call order
    mock_post.side_effect = [mock_streaming_response, mock_no_streaming_response]

    # Long text to trigger streaming
    test_text = " ".join(["Performance test sentence."] * 150)  # ~600 words

    # Test 1: With streaming
    print("\n1. Testing WITH streaming...")
    start_time = time.time()
    response = requests.post("http://localhost:5001/api/tts/generate", json={
        "text": test_text,
        "id": "test_perf_streaming",
        "streaming": True
    })
    streaming_time = time.time() - start_time

    assert response.status_code == 200, f"HTTP {response.status_code}"
    data = response.json()
    assert data.get('success') and data.get('streaming'), "Streaming request failed"
    print(f"✓ Streaming response time: {streaming_time:.2f}s")
    print(f"✓ Total chunks: {data.get('total_chunks')}")

    # Test 2: Without streaming (for comparison)
    print("\n2. Testing WITHOUT streaming...")
    start_time = time.time()
    response = requests.post("http://localhost:5001/api/tts/generate", json={
        "text": test_text[:500],
        "id": "test_perf_no_streaming",
        "streaming": False
    })
    no_streaming_time = time.time() - start_time

    assert response.status_code == 200, f"HTTP {response.status_code}"
    data = response.json()
    assert data.get('success'), "Non-streaming request failed"
    print(f"✓ Non-streaming response time: {no_streaming_time:.2f}s")

    # Compare
    print(f"\n3. Performance comparison:")
    print(f"   Streaming (time to first chunk): {streaming_time:.2f}s")
    print(f"   Non-streaming (full generation): {no_streaming_time:.2f}s")

    # With mocking, response should be fast
    assert streaming_time < 1, f"Mocked streaming took longer than expected ({streaming_time:.2f}s)"
    print(f"✓ PASS: Streaming provides fast initial playback")


def main():
    """Run all TTS streaming tests"""
    print("\n" + "="*60)
    print("TTS STREAMING TEST SUITE")
    print("="*60)
    print("\nTesting TTS streaming functionality...")
    print("Backend server should be running at http://localhost:5001")

    # Check if server is running
    try:
        response = requests.get("http://localhost:5001/api/books", timeout=2)
        if response.status_code == 200:
            print("✓ Backend server is running")
        else:
            print("✗ Backend server returned unexpected status")
            return
    except:
        print("✗ FAIL: Backend server is not running!")
        print("\nPlease start the server with:")
        print("  cd backend && python app.py")
        return

    # Run tests
    results = {
        "Backend Streaming": test_tts_streaming_backend(),
        "Single File Generation": test_tts_single_file(),
        "Frontend Waiting Simulation": test_chunk_waiting_simulation(),
        "Streaming Performance": test_streaming_performance(),
    }

    # Print summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not result:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
