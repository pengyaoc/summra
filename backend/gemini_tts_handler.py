"""Handler for offline TTS generation using Google Gemini 2.5 Flash TTS API"""

import os
import time
import hashlib
import wave
from typing import Optional

try:
    from . import config
    from . import tts_utils  # Shared TTS utilities (provider-agnostic)
except ImportError:
    from backend import config
    from backend import tts_utils

# Google Generative AI SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("Warning: google-genai not available. Gemini TTS functionality will be disabled.")


class RateLimiter:
    """Rate limiter for API requests"""

    def __init__(self, max_requests_per_minute: int, max_tokens_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        self.request_times = []
        self.token_counts = []

    def wait_if_needed(self, estimated_tokens: int = 0):
        """Wait if we're approaching rate limits"""
        current_time = time.time()
        one_minute_ago = current_time - 60

        # Clean old entries
        self.request_times = [t for t in self.request_times if t > one_minute_ago]
        self.token_counts = [(t, c) for t, c in self.token_counts if t > one_minute_ago]

        # Check request rate
        if len(self.request_times) >= self.max_requests:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                print(f"Rate limit approaching - waiting {wait_time:.1f}s...")
                time.sleep(wait_time + 1)
                return self.wait_if_needed(estimated_tokens)

        # Check token rate
        total_tokens = sum(c for _, c in self.token_counts)
        if total_tokens + estimated_tokens > self.max_tokens:
            wait_time = 60 - (current_time - self.token_counts[0][0])
            if wait_time > 0:
                print(f"Token limit approaching - waiting {wait_time:.1f}s...")
                time.sleep(wait_time + 1)
                return self.wait_if_needed(estimated_tokens)

    def record_request(self, tokens_used: int):
        """Record a completed request"""
        current_time = time.time()
        self.request_times.append(current_time)
        self.token_counts.append((current_time, tokens_used))


class GeminiTTSHandler:
    """Handler for Text-to-Speech using Google Gemini 2.5 Flash TTS API"""

    def __init__(self, voice: str = None):
        self.output_dir = config.TTS_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.voice = voice or config.GEMINI_TTS_VOICE
        self.model_name = config.GEMINI_TTS_MODEL

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            config.GEMINI_TTS_MAX_REQUESTS_PER_MINUTE,
            config.GEMINI_TTS_MAX_TOKENS_PER_MINUTE
        )

        # Initialize Gemini client
        if GENAI_AVAILABLE:
            api_key = config.GEMINI_API_KEY
            if not api_key:
                print("Warning: GEMINI_API_KEY environment variable not set - running in preview mode")
                self.client = None
            else:
                try:
                    self.client = genai.Client(api_key=api_key)
                    print(f"Gemini TTS initialized with model: {self.model_name}, voice: {self.voice}")
                except Exception as e:
                    print(f"Error initializing Gemini client: {e}")
                    self.client = None
        else:
            self.client = None

    def estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text (roughly 4 chars per token)"""
        return len(text) // 4

    def generate_audio_chunked(self, text: str, audio_id: str = None) -> Optional[str]:
        """
        Generate audio from text using chunking for long texts.
        Uses configurable chunk size from config.GEMINI_TTS_CHUNK_SIZE_WORDS.
        Shows debug output for each chunk and stitches WAV files together.

        Args:
            text: Text to convert to speech
            audio_id: Unique identifier for caching (optional)

        Returns:
            Path to generated audio file, or None if generation failed
        """
        if not GENAI_AVAILABLE or self.client is None:
            print("Gemini TTS not available")
            return None

        # Generate unique filename for final output
        if audio_id:
            filename = f"{audio_id}_gemini.wav"
        else:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            filename = f"{text_hash}_gemini.wav"

        output_path = self.output_dir / filename

        # Check if audio already exists (caching)
        if output_path.exists():
            print(f"Audio file already exists: {output_path}")
            return str(output_path)

        # Clean text for TTS using shared utility
        cleaned_text = tts_utils.clean_text_for_speech(text)

        if not cleaned_text or cleaned_text.isspace():
            print("Warning: Text is empty after cleaning")
            return None

        # Chunk text at sentence boundaries using shared utility
        chunks = tts_utils.chunk_text_at_sentences(cleaned_text, max_words=config.GEMINI_TTS_CHUNK_SIZE_WORDS)

        print(f"\n{'='*80}")
        print(f"CHUNKING DEBUG - Total chunks: {len(chunks)}")
        print(f"{'='*80}\n")

        chunk_files = []
        max_chunk_retries = 3  # Maximum retries per chunk

        try:
            for i, (chunk_text, word_count, start_pos) in enumerate(chunks, 1):
                # Use shared debug output utility
                next_chunk_text = chunks[i][0] if i < len(chunks) else None
                tts_utils.print_chunking_debug(i, len(chunks), chunk_text, word_count, start_pos, next_chunk_text)

                # Estimate tokens and wait if needed
                estimated_tokens = self.estimate_tokens(chunk_text)
                print(f"\nEstimated tokens: {estimated_tokens}")

                # Retry logic for this chunk
                chunk_success = False
                for chunk_attempt in range(1, max_chunk_retries + 1):
                    try:
                        if chunk_attempt > 1:
                            print(f"\n{'='*80}")
                            print(f"🔄 Retry chunk {i} (attempt {chunk_attempt}/{max_chunk_retries})")
                            print(f"{'='*80}\n")
                            # Wait before retry (exponential backoff)
                            wait_time = 5 * (2 ** (chunk_attempt - 2))  # 5s, 10s...
                            print(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)

                        self.rate_limiter.wait_if_needed(estimated_tokens)

                        # Generate speech for this chunk
                        print(f"\nCalling Gemini TTS API for chunk {i}... (attempt {chunk_attempt})")

                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=chunk_text,
                            config=types.GenerateContentConfig(
                                response_modalities=["AUDIO"],
                                speech_config=types.SpeechConfig(
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=self.voice
                                        )
                                    )
                                )
                            )
                        )

                        # Record the request
                        self.rate_limiter.record_request(estimated_tokens)

                        # Extract PCM audio data from response
                        pcm_data = response.candidates[0].content.parts[0].inline_data.data

                        # Save chunk to temporary file
                        chunk_filename = f"{audio_id}_chunk_{i:03d}.wav" if audio_id else f"chunk_{i:03d}.wav"
                        chunk_path = self.output_dir / chunk_filename

                        with wave.open(str(chunk_path), 'wb') as wf:
                            wf.setnchannels(1)  # Mono
                            wf.setsampwidth(2)  # 16-bit = 2 bytes
                            wf.setframerate(24000)  # 24kHz
                            wf.writeframes(pcm_data)

                        chunk_files.append(str(chunk_path))
                        print(f"✅ Generated chunk audio: {chunk_path} ({len(pcm_data)} bytes)")
                        chunk_success = True
                        break  # Success, exit retry loop

                    except Exception as chunk_error:
                        print(f"❌ Chunk {i} attempt {chunk_attempt}/{max_chunk_retries} failed: {chunk_error}")
                        if chunk_attempt < max_chunk_retries:
                            print(f"Will retry chunk {i}...")
                        else:
                            print(f"❌ Chunk {i} failed after {max_chunk_retries} attempts")
                            import traceback
                            traceback.print_exc()

                if not chunk_success:
                    raise Exception(f"Failed to generate chunk {i} after {max_chunk_retries} attempts")

            # Stitch all chunks together using shared utility
            print(f"\n{'='*80}")
            print(f"STITCHING {len(chunk_files)} CHUNKS")
            print(f"{'='*80}\n")

            tts_utils.stitch_wav_files(chunk_files, str(output_path))

            # Clean up temporary chunk files
            for chunk_file in chunk_files:
                try:
                    os.remove(chunk_file)
                    print(f"Removed temporary file: {chunk_file}")
                except Exception as e:
                    print(f"Warning: Could not remove {chunk_file}: {e}")

            print(f"\n{'='*80}")
            print(f"FINAL OUTPUT: {output_path}")
            print(f"{'='*80}\n")

            return str(output_path)

        except Exception as e:
            print(f"Error generating chunked audio: {e}")
            import traceback
            traceback.print_exc()

            # Clean up any temporary files
            for chunk_file in chunk_files:
                try:
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)
                except Exception:
                    pass

            return None

    def generate_audio(self, text: str, audio_id: str = None) -> Optional[str]:
        """
        Generate audio from text using Gemini TTS API
        Automatically uses chunking for texts over 800 words.

        Args:
            text: Text to convert to speech
            audio_id: Unique identifier for caching (optional)

        Returns:
            Path to generated audio file, or None if generation failed
        """
        if not GENAI_AVAILABLE or self.client is None:
            print("Gemini TTS not available")
            return None

        # Generate unique filename
        if audio_id:
            filename = f"{audio_id}_gemini.wav"
        else:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            filename = f"{text_hash}_gemini.wav"

        output_path = self.output_dir / filename

        # Check if audio already exists (caching)
        if output_path.exists():
            print(f"Audio file already exists: {output_path}")
            return str(output_path)

        # Clean text first using shared utility to check word count
        cleaned_text = tts_utils.clean_text_for_speech(text)

        if not cleaned_text or cleaned_text.isspace():
            print("Warning: Text is empty after cleaning")
            return None

        # Check word count and use chunking if needed
        word_count = len(cleaned_text.split())
        print(f"Generating TTS for {len(cleaned_text)} chars ({word_count} words)")

        if word_count > config.GEMINI_TTS_CHUNK_SIZE_WORDS:
            print(f"Text exceeds {config.GEMINI_TTS_CHUNK_SIZE_WORDS} words - using chunking mode")
            return self.generate_audio_chunked(text, audio_id)

        # For shorter texts, use single API call with retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"\n{'='*80}")
                    print(f"🔄 Retry attempt {attempt}/{max_retries}")
                    print(f"{'='*80}\n")
                    # Wait before retry (exponential backoff)
                    wait_time = 5 * (2 ** (attempt - 2))  # 5s, 10s...
                    print(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)

                # Estimate tokens and wait if needed
                estimated_tokens = self.estimate_tokens(cleaned_text)
                print(f"Estimated tokens: {estimated_tokens}")

                self.rate_limiter.wait_if_needed(estimated_tokens)

                # Generate speech using Gemini TTS API
                print(f"Calling Gemini TTS API with voice: {self.voice} (attempt {attempt})")

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=cleaned_text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=self.voice
                                )
                            )
                        )
                    )
                )

                # Record the request
                self.rate_limiter.record_request(estimated_tokens)

                # Extract PCM audio data from response
                pcm_data = response.candidates[0].content.parts[0].inline_data.data

                # Write WAV file with proper headers
                # Gemini TTS returns PCM at 24kHz, 1 channel, 16-bit
                with wave.open(str(output_path), 'wb') as wf:
                    wf.setnchannels(1)  # Mono
                    wf.setsampwidth(2)  # 16-bit = 2 bytes
                    wf.setframerate(24000)  # 24kHz
                    wf.writeframes(pcm_data)

                print(f"✅ Generated audio: {output_path} ({len(pcm_data)} bytes)")
                return str(output_path)

            except Exception as e:
                print(f"❌ Attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    print(f"Will retry...")
                else:
                    print(f"❌ Failed after {max_retries} attempts")
                    import traceback
                    traceback.print_exc()

        # All retries failed
        print(f"No audio data generated after {max_retries} attempts")
        return None
