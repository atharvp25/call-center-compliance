"""
block_1_stt.py — Speech-to-Text using Sarvam AI
Handles Hindi (Hinglish) & Tamil (Tanglish) audio with chunked processing.
Includes retry logic and robust error handling for production reliability.
"""

import requests
import os
import time
import tempfile
from pydub import AudioSegment


# ── Sarvam API Configuration ────────────────────────────────────────────
SARVAM_API_URL = "https://api.sarvam.ai/speech-to-text"
CHUNK_LENGTH_MS = 25_000  # 25 seconds (safely under Sarvam's 30s limit)
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# Language code mapping for Sarvam AI
LANGUAGE_MAP = {
    "tamil": "ta-IN",
    "ta-in": "ta-IN",
    "tanglish": "ta-IN",
    "hindi": "hi-IN",
    "hi-in": "hi-IN",
    "hinglish": "hi-IN",
}


def _get_language_code(language_preference: str) -> str:
    """Maps language preference string to Sarvam language code."""
    return LANGUAGE_MAP.get(language_preference.lower().strip(), "hi-IN")


def _transcribe_chunk(chunk_path: str, lang_code: str, api_key: str,
                      chunk_index: int, total_chunks: int) -> str:
    """
    Sends a single audio chunk to Sarvam AI with retry logic.
    Returns the transcript text for this chunk, or empty string on failure.
    """
    headers = {"api-subscription-key": api_key}
    data = {"language_code": lang_code}

    for attempt in range(MAX_RETRIES):
        try:
            print(f"[STT] Sending chunk {chunk_index + 1}/{total_chunks} "
                  f"(attempt {attempt + 1}/{MAX_RETRIES})...")

            with open(chunk_path, "rb") as audio_file:
                files = {"file": (f"chunk_{chunk_index}.mp3", audio_file, "audio/mpeg")}
                response = requests.post(
                    SARVAM_API_URL,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30,
                )

            if response.status_code == 200:
                transcript = response.json().get("transcript", "")
                if transcript:
                    print(f"[STT] Chunk {chunk_index + 1} transcribed: "
                          f"{len(transcript)} chars")
                return transcript

            print(f"[STT] API error on chunk {chunk_index + 1}: "
                  f"{response.status_code} — {response.text[:200]}")

        except requests.exceptions.RequestException as e:
            print(f"[STT] Network error on chunk {chunk_index + 1}: {str(e)}")

        # Wait before retry (except on last attempt)
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

    print(f"[STT] WARNING: All {MAX_RETRIES} attempts failed for chunk {chunk_index + 1}")
    return ""


def process_audio_file_sarvam_chunked(file_path: str, language_preference: str) -> str:
    """
    Processes an audio file through Sarvam AI Speech-to-Text.

    1. Loads the MP3 audio file
    2. Cuts it into 25-second chunks (under Sarvam's 30s limit)
    3. Sends each chunk to Sarvam AI with retry logic
    4. Combines all chunk transcripts into a single text

    Args:
        file_path: Path to the MP3 audio file
        language_preference: Language of the audio ("Tamil", "Hindi", etc.)

    Returns:
        Complete transcript text, or error string starting with "Error:"
    """
    if not os.path.exists(file_path):
        return "Error: File not found."

    # ── Validate API key ────────────────────────────────────────────────
    api_key = os.getenv("SARVAM_API_KEY", "")
    if not api_key:
        return "Error: SARVAM_API_KEY environment variable not set."

    # ── Load and chunk audio ────────────────────────────────────────────
    print(f"[STT] Loading audio from {file_path}...")
    try:
        audio = AudioSegment.from_mp3(file_path)
    except Exception as e:
        return f"Error: Failed to load audio file — {str(e)}"

    lang_code = _get_language_code(language_preference)
    is_tamil = (lang_code == "ta-IN")
    
    # Use overlap for non-Tamil to fix chunk boundary clipping 
    # without affecting existing Tamil performance.
    overlap_ms = 0 if is_tamil else 1000
    step_size = CHUNK_LENGTH_MS - overlap_ms

    chunks = [audio[i:i + CHUNK_LENGTH_MS]
              for i in range(0, len(audio), step_size)]

    print(f"[STT] Audio loaded: {len(audio) / 1000:.1f}s, "
          f"split into {len(chunks)} chunks, language: {lang_code}")

    # ── Process each chunk concurrently ──────────────────────────────────
    transcript_parts = [""] * len(chunks)

    from concurrent.futures import ThreadPoolExecutor

    def process_single_chunk(args):
        i, chunk = args
        # Save chunk to temp file safely inside the thread
        tmp_fd, chunk_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)

        try:
            chunk.export(chunk_path, format="mp3")
            transcript_piece = _transcribe_chunk(
                chunk_path, lang_code, api_key, i, len(chunks)
            )
            return i, transcript_piece
        except Exception as e:
            print(f"[STT] Error processing chunk {i + 1}: {str(e)}")
            return i, ""
        finally:
            try:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
            except OSError:
                pass

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_single_chunk, enumerate(chunks))

    for idx, piece in results:
        if piece:
            transcript_parts[idx] = piece

    # ── Combine results ─────────────────────────────────────────────────
    full_transcript = " ".join([p for p in transcript_parts if p]).strip()

    if not full_transcript:
        return "Error: No transcript could be generated from audio."

    print(f"[STT] Transcription complete: {len(full_transcript)} chars "
          f"from {len(transcript_parts)}/{len(chunks)} chunks")
    return full_transcript
