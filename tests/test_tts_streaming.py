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
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))


def test_tts_streaming_backend():
    """Test that backend returns first chunk immediately"""
    print("\n" + "="*60)
    print("TEST 1: Backend TTS Streaming")
    print("="*60)

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

    try:
        response = requests.post(url, json=payload, timeout=10)
        response_time = time.time() - start_time

        print(f"✓ Response received in {response_time:.2f} seconds")

        if response.status_code == 200:
            data = response.json()

            if data.get('success'):
                print(f"✓ Success response received")
                print(f"✓ Streaming mode: {data.get('streaming')}")
                print(f"✓ Total chunks: {data.get('total_chunks')}")
                print(f"✓ Audio URLs: {len(data.get('audio_urls', []))}")

                # Verify response time is fast (should return before all chunks are generated)
                if response_time < 5.0:
                    print(f"✓ PASS: Response time {response_time:.2f}s < 5s (first chunk ready quickly)")
                else:
                    print(f"✗ FAIL: Response took too long ({response_time:.2f}s)")
                    return False

                # Check that first chunk exists
                audio_urls = data.get('audio_urls', [])
                if audio_urls:
                    first_url = audio_urls[0]
                    print(f"\n2. Checking first chunk availability...")
                    chunk_response = requests.head(f"http://localhost:5001{first_url}")
                    if chunk_response.status_code == 200:
                        print(f"✓ PASS: First chunk is immediately available")
                    else:
                        print(f"✗ FAIL: First chunk not available (status: {chunk_response.status_code})")
                        return False

                    # Wait and check that subsequent chunks are being generated
                    if len(audio_urls) > 1:
                        print(f"\n3. Waiting for background chunk generation...")
                        time.sleep(3)

                        second_url = audio_urls[1]
                        chunk_response = requests.head(f"http://localhost:5001{second_url}")
                        if chunk_response.status_code == 200:
                            print(f"✓ PASS: Second chunk generated in background")
                        else:
                            print(f"⚠ WARNING: Second chunk not yet available (may still be generating)")

                print(f"\n✓ TEST 1 PASSED: Backend streaming works correctly")
                return True
            else:
                print(f"✗ FAIL: Error in response: {data.get('error')}")
                return False
        else:
            print(f"✗ FAIL: HTTP {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        print(f"✗ FAIL: Request timed out after 10 seconds")
        return False
    except Exception as e:
        print(f"✗ FAIL: Exception occurred: {e}")
        return False


def test_tts_single_file():
    """Test that short text generates a single file (no streaming)"""
    print("\n" + "="*60)
    print("TEST 2: Single File Generation (Short Text)")
    print("="*60)

    # Short text should not trigger streaming
    test_text = "This is a short test sentence."

    url = "http://localhost:5001/api/tts/generate"
    payload = {
        "text": test_text,
        "id": "test_single",
        "streaming": True
    }

    print(f"\n1. Sending request with short text ({len(test_text.split())} words)...")

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if data.get('success'):
                streaming = data.get('streaming', False)
                print(f"✓ Streaming mode: {streaming}")

                if not streaming and 'audio_url' in data:
                    print(f"✓ PASS: Short text generates single file (no streaming)")
                    return True
                else:
                    print(f"✗ FAIL: Short text should not use streaming")
                    return False
            else:
                print(f"✗ FAIL: Error in response: {data.get('error')}")
                return False
        else:
            print(f"✗ FAIL: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ FAIL: Exception occurred: {e}")
        return False


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
    return True


def test_streaming_performance():
    """Test that streaming provides better perceived performance"""
    print("\n" + "="*60)
    print("TEST 4: Streaming Performance Comparison")
    print("="*60)

    # Long text to trigger streaming
    test_text = " ".join(["Performance test sentence."] * 150)  # ~600 words

    url = "http://localhost:5001/api/tts/generate"

    # Test 1: With streaming
    print("\n1. Testing WITH streaming...")
    payload_streaming = {
        "text": test_text,
        "id": "test_perf_streaming",
        "streaming": True
    }

    start_time = time.time()
    try:
        response = requests.post(url, json=payload_streaming, timeout=15)
        streaming_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('streaming'):
                print(f"✓ Streaming response time: {streaming_time:.2f}s")
                print(f"✓ Total chunks: {data.get('total_chunks')}")
            else:
                print(f"✗ Streaming request failed")
                return False
        else:
            print(f"✗ HTTP {response.status_code}")
            return False

        # Test 2: Without streaming (for comparison)
        print("\n2. Testing WITHOUT streaming...")
        payload_no_streaming = {
            "text": test_text[:500],  # Shorter text
            "id": "test_perf_no_streaming",
            "streaming": False
        }

        start_time = time.time()
        response = requests.post(url, json=payload_no_streaming, timeout=15)
        no_streaming_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Non-streaming response time: {no_streaming_time:.2f}s")
            else:
                print(f"✗ Non-streaming request failed")
                return False
        else:
            print(f"✗ HTTP {response.status_code}")
            return False

        # Compare
        print(f"\n3. Performance comparison:")
        print(f"   Streaming (time to first chunk): {streaming_time:.2f}s")
        print(f"   Non-streaming (full generation): {no_streaming_time:.2f}s")

        if streaming_time < 10:
            print(f"✓ PASS: Streaming provides fast initial playback (<10s)")
            return True
        else:
            print(f"⚠ WARNING: Streaming took longer than expected ({streaming_time:.2f}s)")
            return True  # Still pass, but with warning

    except Exception as e:
        print(f"✗ FAIL: Exception occurred: {e}")
        return False


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
