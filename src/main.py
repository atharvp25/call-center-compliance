"""
main.py — Production-Ready FastAPI backend for CALL Analytics
HCL x Guvi Hackathon | Enterprise Call Center QA Pipeline

Architecture:
  Audio (Base64) → Sarvam STT → Gemini LLM Analysis → Sanitized JSON Response
  ChromaDB stores every processed call as a searchable semantic audit trail.
  Celery available for asynchronous batch processing of recordings.
"""

# ── Load environment variables from .env FIRST ──────────────────────────
from dotenv import load_dotenv
from pathlib import Path

# Ensure .env is found from project root regardless of working directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

import os
import base64
import tempfile
import traceback
from typing import List

from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Import the three AI blocks ──────────────────────────────────────────
try:
    from .block_1_stt import process_audio_file_sarvam_chunked
    from .block_2_vector import store_call_transcript, search_audit_store, get_audit_stats
    from .block_3_llm import call_llm_for_final_json
except ImportError:
    # Fallback for direct execution (python src/main.py)
    from block_1_stt import process_audio_file_sarvam_chunked
    from block_2_vector import store_call_transcript, search_audit_store, get_audit_stats
    from block_3_llm import call_llm_for_final_json

# ── Configuration ───────────────────────────────────────────────────────
VALID_API_KEY = os.getenv("CALL_API_KEY", "hcl-guvi-hackathon-2026")

# ── FastAPI App ─────────────────────────────────────────────────────────
app = FastAPI(
    title="CALL Analytics API",
    description="AI-powered Call Center Quality Assurance & Analytics Engine",
    version="1.0.0",
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
#  Pydantic Models — enforce the EXACT response schema the evaluator expects
# ═══════════════════════════════════════════════════════════════════════════

class CallRequest(BaseModel):
    language: str
    audioFormat: str
    audioBase64: str


class SOPValidation(BaseModel):
    greeting: bool = False
    identification: bool = False
    problemStatement: bool = False
    solutionOffering: bool = False
    closing: bool = False
    complianceScore: float = Field(0.0, ge=0.0, le=1.0)
    adherenceStatus: str = "NOT_FOLLOWED"
    explanation: str = ""


class Analytics(BaseModel):
    paymentPreference: str = "FULL_PAYMENT"
    rejectionReason: str = "NONE"
    sentiment: str = "Neutral"


class CallAnalyticsResponse(BaseModel):
    status: str = "success"
    language: str = ""
    transcript: str = ""
    summary: str = ""
    sop_validation: SOPValidation = SOPValidation()
    analytics: Analytics = Analytics()
    keywords: List[str] = []


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str = ""


# ═══════════════════════════════════════════════════════════════════════════
#  Global Exception Handler — API must NEVER return non-JSON
# ═══════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": f"Internal server error: {type(exc).__name__}"},
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Allowed-value guards (clamp LLM outputs to strict enums)
# ═══════════════════════════════════════════════════════════════════════════

ALLOWED_PAYMENT = {"EMI", "FULL_PAYMENT", "PARTIAL_PAYMENT", "DOWN_PAYMENT"}
ALLOWED_REJECTION = {"HIGH_INTEREST", "BUDGET_CONSTRAINTS", "ALREADY_PAID", "NOT_INTERESTED", "NONE"}
ALLOWED_SENTIMENT = {"Positive", "Neutral", "Negative"}
ALLOWED_ADHERENCE = {"FOLLOWED", "NOT_FOLLOWED"}

# SOP boolean field names (in order)
SOP_BOOL_FIELDS = ("greeting", "identification", "problemStatement", "solutionOffering", "closing")


def _sanitize_llm_output(llm_data: dict) -> dict:
    """
    Ensures every LLM-generated value falls within the strict allowed sets,
    and RECALCULATES complianceScore + adherenceStatus in Python.
    Never trust LLM math — LLMs frequently miscalculate fractions.
    """
    # ── Handle error responses from LLM ─────────────────────────────
    if not isinstance(llm_data, dict):
        llm_data = {}

    # ── analytics ───────────────────────────────────────────────────
    analytics = llm_data.get("analytics", {})
    if not isinstance(analytics, dict):
        analytics = {}
    if analytics.get("paymentPreference") not in ALLOWED_PAYMENT:
        analytics["paymentPreference"] = "FULL_PAYMENT"
    if analytics.get("rejectionReason") not in ALLOWED_REJECTION:
        analytics["rejectionReason"] = "NONE"
    if analytics.get("sentiment") not in ALLOWED_SENTIMENT:
        analytics["sentiment"] = "Neutral"
    llm_data["analytics"] = analytics

    # ── sop_validation ──────────────────────────────────────────────
    sop = llm_data.get("sop_validation", {})
    if not isinstance(sop, dict):
        sop = {}

    # Force boolean values for each SOP field
    # Safety: handle string "false"/"true" from LLM (bool("false") is True in Python!)
    for field in SOP_BOOL_FIELDS:
        val = sop.get(field, False)
        if isinstance(val, str):
            sop[field] = val.lower().strip() in ("true", "1", "yes")
        else:
            sop[field] = bool(val)

    # ── CRITICAL: Calculate complianceScore in Python, NOT from LLM ──
    
    true_count = sum(sop[f] for f in SOP_BOOL_FIELDS)
    sop["complianceScore"] = round(true_count / 5.0, 2)

    # ── Derive adherenceStatus from the boolean fields ──────────────
    sop["adherenceStatus"] = "FOLLOWED" if true_count == 5 else "NOT_FOLLOWED"

    # Ensure explanation exists
    sop.setdefault("explanation", "")
    if not isinstance(sop["explanation"], str):
        sop["explanation"] = str(sop["explanation"])

    llm_data["sop_validation"] = sop

    # ── keywords ────────────────────────────────────────────────────
    kw = llm_data.get("keywords", [])
    if not isinstance(kw, list):
        kw = []
    # Filter out empty/null values and ensure all are strings
    llm_data["keywords"] = [str(k).strip() for k in kw if k and str(k).strip()]

    # Ensure at least some keywords exist
    if not llm_data["keywords"]:
        llm_data["keywords"] = ["call center", "compliance"]

    # ── summary ─────────────────────────────────────────────────────
    llm_data.setdefault("summary", "")
    if not isinstance(llm_data["summary"], str):
        llm_data["summary"] = str(llm_data["summary"])

    return llm_data


# ═══════════════════════════════════════════════════════════════════════════
#  Helper — safe cleanup of temp file
# ═══════════════════════════════════════════════════════════════════════════

def _cleanup_temp_file(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  Main Endpoint — POST /api/call-analytics
# ═══════════════════════════════════════════════════════════════════════════

@app.post(
    "/",
    response_model=CallAnalyticsResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
@app.post(
    "/api/call-analytics",
    response_model=CallAnalyticsResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def call_analytics(
    payload: CallRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None, alias="x-api-key"),
):
    """
    Process a call recording and return structured compliance analysis.

    Pipeline: Base64 Audio → Sarvam STT → Gemini Analysis → Sanitized JSON
    """
    # ── 1. Validate API key ─────────────────────────────────────────
    if not x_api_key or x_api_key != VALID_API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Unauthorized – invalid or missing API key"},
        )

    temp_audio_path = None

    try:
        # ── 2. Decode Base64 audio & save to temp file ──────────────
        try:
            audio_bytes = base64.b64decode(payload.audioBase64)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "Invalid Base64 audio data"},
            )

        if len(audio_bytes) < 100:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "Audio data too small — likely invalid"},
            )

        tmp_fd, temp_audio_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)
        with open(temp_audio_path, "wb") as f:
            f.write(audio_bytes)

        print(f"[API] Processing {len(audio_bytes)} bytes of {payload.language} audio...")

        # ── 3. Block 1 — Speech-to-Text (Sarvam AI) ────────────────
        transcript_text = process_audio_file_sarvam_chunked(
            temp_audio_path, payload.language
        )
        if not transcript_text or transcript_text.startswith("Error"):
            raise ValueError(f"STT failed: {transcript_text}")

        print(f"[API] Transcript generated: {len(transcript_text)} chars")

        # ── 4. Block 3 — LLM Analysis (Gemini) ─────────────────────
        llm_data = call_llm_for_final_json(transcript_text)

        # ── 5. Sanitize LLM outputs + recalculate compliance ───────
        llm_data = _sanitize_llm_output(llm_data)

        # ── 6. Block 2 — Store in ChromaDB audit trail in background ──────
        def safe_store_audit():
            try:
                store_call_transcript(
                    transcript=transcript_text,
                    language=payload.language,
                    compliance_score=llm_data["sop_validation"]["complianceScore"],
                    payment_preference=llm_data["analytics"]["paymentPreference"],
                    sentiment=llm_data["analytics"]["sentiment"],
                )
            except Exception as e:
                print(f"[API] Warning: Audit storage failed — {str(e)}")
                
        background_tasks.add_task(safe_store_audit)

        # ── 7. Build the EXACT response schema ──────────────────────
        response = CallAnalyticsResponse(
            status="success",
            language=payload.language,
            transcript=transcript_text,
            summary=llm_data.get("summary", ""),
            sop_validation=SOPValidation(**llm_data.get("sop_validation", {})),
            analytics=Analytics(**llm_data.get("analytics", {})),
            keywords=llm_data.get("keywords", []),
        )

        print(f"[API] Response ready — compliance: "
              f"{response.sop_validation.complianceScore}, "
              f"payment: {response.analytics.paymentPreference}")

        return response

    except HTTPException:
        raise

    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc)},
        )

    finally:
        _cleanup_temp_file(temp_audio_path)


# ═══════════════════════════════════════════════════════════════════════════
#  Health Check + Audit Stats
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """Health check endpoint — verifies the API is running."""
    return {"status": "ok", "service": "CALL Analytics API", "version": "1.0.0"}


@app.get("/audit/stats")
async def audit_stats():
    """Returns statistics about the semantic audit store."""
    return get_audit_stats()


@app.get("/audit/search")
async def audit_search(q: str = "payment"):
    """Search the semantic audit store for similar historical calls."""
    results = search_audit_store(q, n_results=5)
    return {"query": q, "results_count": len(results), "results": results}


# ── Serve Frontend Dashboard ──────────────────────────────────────────
from fastapi.responses import FileResponse
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ── Run with: uvicorn src.main:app --host 0.0.0.0 --port 8000 ──────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
