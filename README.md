# Call Center Compliance API

AI-powered Call Center Quality Assurance & Analytics Engine built for the **HCL x Guvi Hackathon**.

## Description

This system processes voice recordings from call centers in **Hindi (Hinglish)** and **Tamil (Tanglish)**, extracts text using speech-to-text, validates calls against standard operating procedures (SOP), and categorizes payment preferences — all through a single REST API endpoint.

### Architecture & Strategy

We designed a **three-stage AI pipeline** optimized for accuracy, reliability, and speed:

```
Audio (Base64 MP3)
     │
     ▼
┌─────────────────────────────────┐
│  Block 1 — Speech-to-Text      │  Sarvam AI (Indian language specialist)
│  25s chunked processing         │  Handles Tanglish & Hinglish natively
│  3x retry with backoff          │
└─────────────┬───────────────────┘
              │ Full Transcript
              ▼
┌─────────────────────────────────┐
│  Block 3 — LLM Analysis        │  Google Gemini 2.5 Flash (JSON mode)
│  SOP validation (5-step check)  │  Low temperature for consistency
│  Payment & rejection classify   │  Structured output guaranteed
│  Sentiment + keyword extract    │
└─────────────┬───────────────────┘
              │ Structured JSON
              ▼
┌─────────────────────────────────┐
│  Python Sanitization Layer      │  Recalculates complianceScore
│  Enum clamping & validation     │  Derives adherenceStatus
│  Type coercion & defaults       │  Guarantees schema compliance
└─────────────┬───────────────────┘
              │ Validated Data
              ▼
┌─────────────────────────────────┐
│  Block 2 — Semantic Audit Store │  ChromaDB (persistent)
│  Multilingual embeddings        │  Searchable call history
│  Rich metadata indexing         │  Analytics dashboard ready
└─────────────────────────────────┘
```

### Key Design Decisions

1. **Sarvam AI over Whisper:** We chose Sarvam AI for STT because it is purpose-built for Indian languages and handles code-mixed speech (Tanglish/Hinglish) significantly better than general-purpose models like Whisper.

2. **Classification over RAG:** We initially prototyped a full RAG pipeline but identified that SOP compliance detection is fundamentally a **classification problem**, not a retrieval problem. Sending the full transcript to Gemini for direct analysis gives better accuracy and lower latency than chunking-and-retrieving from a small single document.

3. **ChromaDB as Audit Store:** ChromaDB serves as a **persistent semantic audit store** — every processed call is indexed with compliance metadata (score, language, payment preference, sentiment) for searchable analytics across all historical calls. The `paraphrase-multilingual-MiniLM-L12-v2` embedding model handles Tamil, Hindi, and English in a single vector space.

4. **Python-calculated compliance:** `complianceScore` and `adherenceStatus` are always calculated in Python (`sum(booleans) / 5`), never trusted from the LLM. LLMs frequently miscalculate fractions — this deterministic approach guarantees correct scores.

5. **Celery for async processing:** The system supports Celery-based asynchronous processing for high-throughput batch scenarios, while the API endpoint processes synchronously for immediate response.

### Reliability & Safety Features

- **Gemini JSON mode** — `response_mime_type="application/json"` guarantees valid JSON output, eliminating parse failures
- **Enum sanitization layer** — Every LLM output is clamped to strict allowed values (payment types, rejection reasons, sentiment)
- **Global exception handler** — The API never returns a non-JSON response, even on unexpected errors
- **Retry logic with backoff** — Both Sarvam STT (3x) and Gemini (3x) retry with exponential backoff
- **Temp file safety** — Uses `tempfile.mkstemp()` for deploy-safe file handling (works on read-only filesystems)
- **Configurable timeouts** — Gemini client has a 120-second timeout to prevent hanging requests

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language/Framework** | Python 3.10+ / FastAPI | High-performance async API server |
| **Speech-to-Text** | Sarvam AI | Optimized for Indian languages (Hindi, Tamil) |
| **LLM** | Google Gemini 2.5 Flash | Structured compliance analysis with JSON mode |
| **Vector Database** | ChromaDB | Persistent semantic audit store with multilingual embeddings |
| **Embeddings** | HuggingFace `paraphrase-multilingual-MiniLM-L12-v2` | Multilingual sentence embeddings |
| **Async Processing** | Celery + Redis | Background voice processing for batch workloads |
| **Schema Enforcement** | Pydantic v2 | Guarantees exact JSON response structure |

## Setup Instructions

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd call-center-compliance
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** FFmpeg is required for audio processing. Install it via:
> - Linux: `apt install ffmpeg`
> - Mac: `brew install ffmpeg`
> - Windows: Download from [ffmpeg.org](https://ffmpeg.org/)

### 3. Set environment variables
```bash
cp .env.example .env
# Edit .env and add your actual API keys
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SARVAM_API_KEY` | ✅ | Sarvam AI API key for speech-to-text |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key for LLM analysis |
| `CALL_API_KEY` | ✅ | API authentication key (shared with evaluators) |
| `GEMINI_MODEL` | Optional | Gemini model name (default: `gemini-2.5-flash`) |
| `GEMINI_TIMEOUT_MS` | Optional | LLM timeout in ms (default: `120000`) |
| `CHROMA_PERSIST_DIR` | Optional | ChromaDB storage path (default: system temp) |
| `PORT` | Optional | Server port (default: `8000`) |

### 4. Run the application
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 5. (Optional) Start Celery worker for async processing
```bash
celery -A src.celery_tasks worker --loglevel=info
```

## API Usage

### Endpoint
```
POST /api/call-analytics
```

### Headers
```
Content-Type: application/json
x-api-key: YOUR_API_KEY
```

### Request Body
```json
{
  "language": "Tamil",
  "audioFormat": "mp3",
  "audioBase64": "BASE64_ENCODED_AUDIO_STRING"
}
```

### cURL Example
```bash
curl -X POST https://your-domain.com/api/call-analytics \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "language": "Tamil",
    "audioFormat": "mp3",
    "audioBase64": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU2LjM2..."
  }'
```

### Response
```json
{
  "status": "success",
  "language": "Tamil",
  "transcript": "Full speech-to-text output in original language...",
  "summary": "Concise AI summary of the conversation",
  "sop_validation": {
    "greeting": true,
    "identification": true,
    "problemStatement": true,
    "solutionOffering": true,
    "closing": true,
    "complianceScore": 1.0,
    "adherenceStatus": "FOLLOWED",
    "explanation": "All SOP steps were properly followed by the agent."
  },
  "analytics": {
    "paymentPreference": "EMI",
    "rejectionReason": "NONE",
    "sentiment": "Positive"
  },
  "keywords": ["Guvi Institution", "Data Science", "EMI", "placement", "certification"]
}
```

### Additional Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check — verifies the API is running |
| `/audit/stats` | GET | Returns count of calls stored in the semantic audit store |
| `/audit/search?q=payment` | GET | Semantic search across historical call transcripts |

## Project Structure
```
├── src/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # FastAPI server — request handling, schema enforcement
│   ├── block_1_stt.py        # Speech-to-Text — Sarvam AI with chunked processing
│   ├── block_2_vector.py     # Semantic Audit Store — ChromaDB with multilingual embeddings
│   ├── block_3_llm.py        # LLM Analysis — Gemini structured JSON generation
│   └── celery_tasks.py       # Async voice processing tasks (Celery)
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
├── Procfile                  # Deployment configuration
└── README.md                 # This file
```

## Approach

Our approach prioritizes **accuracy and reliability over complexity**:

1. **Indian-first STT** — Sarvam AI handles Tanglish/Hinglish natively, avoiding the accuracy loss of general-purpose models on code-mixed Indian speech.

2. **Direct classification** — Full transcript analysis via Gemini with structured JSON mode, constrained to exact allowed categories. No unnecessary retrieval overhead.

3. **Deterministic scoring** — Compliance scores are calculated mathematically in Python, not generated by the LLM. This eliminates hallucinated or miscalculated scores.

4. **Defense in depth** — Every stage has fallbacks: STT retries, LLM retries, enum clamping, global error handling. The API never crashes, never returns invalid JSON, and never returns out-of-spec values.

5. **Semantic audit trail** — ChromaDB stores every processed call with rich metadata, enabling semantic search across all historical calls for pattern analysis and compliance monitoring.
