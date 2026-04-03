"""
celery_tasks.py — Asynchronous voice processing tasks using Celery
Enables background processing of call recordings for high-throughput scenarios.

Usage:
    Start worker:  celery -A src.celery_tasks worker --loglevel=info
    The main API can dispatch tasks to this worker for async processing.
"""

import os
import base64
import tempfile
from celery import Celery

# ── Celery Configuration ────────────────────────────────────────────────
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "call_analytics",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=300,  # 5 minute hard limit per task
    task_soft_time_limit=240,  # 4 minute soft limit
)


@celery_app.task(name="process_call_async", bind=True, max_retries=2)
def process_call_async(self, audio_base64: str, language: str) -> dict:
    """
    Process a call recording asynchronously through the full AI pipeline.

    Pipeline: Base64 Audio → Decode → Sarvam STT → Gemini Analysis → ChromaDB Storage

    Args:
        audio_base64: Base64-encoded MP3 audio data
        language: Language of the audio ("Tamil" or "Hindi")

    Returns:
        Dictionary with processing results and status
    """
    # Lazy imports to avoid loading heavy models at worker startup
    from .block_1_stt import process_audio_file_sarvam_chunked
    from .block_2_vector import store_call_transcript
    from .block_3_llm import call_llm_for_final_json

    temp_path = None

    try:
        # ── Decode audio ────────────────────────────────────────────
        audio_bytes = base64.b64decode(audio_base64)
        tmp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)

        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        # ── Speech-to-Text ──────────────────────────────────────────
        transcript = process_audio_file_sarvam_chunked(temp_path, language)
        if not transcript or transcript.startswith("Error"):
            return {"status": "error", "message": transcript or "STT failed"}

        # ── LLM Analysis ───────────────────────────────────────────
        llm_data = call_llm_for_final_json(transcript)

        # ── Store in audit trail ────────────────────────────────────
        sop = llm_data.get("sop_validation", {})
        analytics = llm_data.get("analytics", {})
        store_call_transcript(
            transcript=transcript,
            language=language,
            compliance_score=sop.get("complianceScore", 0.0),
            payment_preference=analytics.get("paymentPreference", "FULL_PAYMENT"),
            sentiment=analytics.get("sentiment", "Neutral"),
        )

        return {
            "status": "success",
            "transcript_length": len(transcript),
            "compliance_score": sop.get("complianceScore", 0.0),
        }

    except Exception as exc:
        # Retry on transient failures
        raise self.retry(exc=exc, countdown=10)

    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
