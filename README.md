# 📞 CALL Analytics — AI Call Center Compliance Engine

> **HCL x Guvi Hackathon 2026** — Enterprise-grade Call Center Quality Assurance & Analytics

AI-powered system that processes call center voice recordings in **Hindi (Hinglish)** and **Tamil (Tanglish)**, validates agent compliance against Standard Operating Procedures (SOP), and returns structured analytics — all through a single REST API endpoint with a premium web dashboard.

---

## 🏗️ Architecture

We designed a **three-stage Micro-RAG pipeline** optimized for accuracy, reliability, and speed:

```
Audio (Base64 MP3)
     │
     ▼
┌─────────────────────────────────┐
│  Block 1 — Speech-to-Text      │  Sarvam AI (Indian language specialist)
│  Parallel chunked processing    │  Handles Tanglish & Hinglish natively
│  ThreadPoolExecutor (5 workers) │  3x retry with backoff
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
│  Block 2 — Semantic Audit Store │  ChromaDB (persistent vector DB)
│  Multilingual embeddings        │  Searchable call history
│  Background task execution      │  Zero impact on response time
└─────────────────────────────────┘
```

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Python 3.10+ / FastAPI | High-performance async API server |
| **Speech-to-Text** | Sarvam AI | Optimized for Indian languages (Hindi, Tamil) |
| **LLM** | Google Gemini 2.5 Flash | Structured compliance analysis with JSON mode |
| **Vector Database** | ChromaDB | Persistent semantic audit store with multilingual embeddings |
| **Embeddings** | `paraphrase-multilingual-MiniLM-L12-v2` | Multilingual sentence embeddings (Hindi, Tamil, English) |
| **Schema** | Pydantic v2 | Strict JSON response structure enforcement |
| **Frontend** | HTML5, CSS3, JavaScript | Premium glassmorphism dashboard with real-time API integration |
| **Deployment** | Docker / Hugging Face Spaces | Containerized production deployment |

## ⚡ Key Design Decisions

1. **Sarvam AI over Whisper** — Purpose-built for Indian languages; handles code-mixed speech (Tanglish/Hinglish) far better than general-purpose models.

2. **Parallel STT Processing** — Audio chunks are transcribed concurrently using `ThreadPoolExecutor`, reducing STT time from ~28s to ~12s.

3. **Classification over RAG** — SOP compliance is a classification problem. Direct transcript analysis via Gemini gives better accuracy than chunking-and-retrieving.

4. **Python-calculated compliance** — `complianceScore` and `adherenceStatus` are always calculated deterministically in Python (`sum(booleans) / 5`), never trusted from the LLM.

5. **ChromaDB as Background Audit Store** — Every call is indexed with compliance metadata via FastAPI `BackgroundTasks`, adding zero latency to the response path.

## 🔒 Reliability & Safety

- **Gemini JSON mode** — `response_mime_type="application/json"` guarantees valid JSON output
- **Enum sanitization** — Every LLM output is clamped to strict allowed values
- **Global exception handler** — API never returns non-JSON, even on crashes
- **Retry with backoff** — Both Sarvam STT (3x) and Gemini (3x) retry automatically
- **Temp file safety** — `tempfile.mkstemp()` for read-only filesystem compatibility

---

## 📁 Project Structure

```
├── src/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # FastAPI server — routing, schema enforcement, BackgroundTasks
│   ├── block_1_stt.py        # Speech-to-Text — Sarvam AI with parallel chunk processing
│   ├── block_2_vector.py     # Semantic Audit Store — ChromaDB with multilingual embeddings
│   ├── block_3_llm.py        # LLM Analysis — Gemini structured JSON generation
│   └── celery_tasks.py       # Async batch processing tasks (Celery)
├── frontend/
│   ├── index.html            # Dashboard UI — glassmorphism design
│   ├── style.css             # Premium dark-mode stylesheet
│   └── script.js             # API integration, drag-drop, live results rendering
├── requirements.txt          # Python dependencies
├── Dockerfile                # Production container configuration
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/atharvp25/call-center-compliance.git
cd call-center-compliance
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** FFmpeg is required for audio processing:
> - Linux: `apt install ffmpeg`
> - Mac: `brew install ffmpeg`
> - Windows: Download from [ffmpeg.org](https://ffmpeg.org/)

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SARVAM_API_KEY` | ✅ | Sarvam AI API key for STT |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key for LLM |
| `CALL_API_KEY` | ✅ | API auth key (shared with evaluators) |
| `GEMINI_MODEL` | Optional | Model name (default: `gemini-2.5-flash`) |
| `PORT` | Optional | Server port (default: `8000`) |

### 4. Run the API server
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 5. Open the Dashboard
```
Open frontend/index.html in your browser
```

---

## 📡 API Reference

### `POST /api/call-analytics`

**Headers:**
```
Content-Type: application/json
x-api-key: YOUR_API_KEY
```

**Request Body:**
```json
{
  "language": "Tamil",
  "audioFormat": "mp3",
  "audioBase64": "BASE64_ENCODED_AUDIO"
}
```

**Response:**
```json
{
  "status": "success",
  "language": "Tamil",
  "transcript": "Full speech-to-text output...",
  "summary": "AI-generated conversation summary",
  "sop_validation": {
    "greeting": true,
    "identification": true,
    "problemStatement": true,
    "solutionOffering": true,
    "closing": true,
    "complianceScore": 1.0,
    "adherenceStatus": "FOLLOWED",
    "explanation": "All SOP steps were properly followed."
  },
  "analytics": {
    "paymentPreference": "EMI",
    "rejectionReason": "NONE",
    "sentiment": "Positive"
  },
  "keywords": ["Data Analytics", "EMI", "placement", "certification"]
}
```

### Additional Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/audit/stats` | GET | ChromaDB audit store statistics |
| `/audit/search?q=payment` | GET | Semantic search across historical calls |

---

## 🎯 Approach

1. **Indian-first STT** — Sarvam AI handles Tanglish/Hinglish natively with high accuracy
2. **Direct classification** — Full transcript → Gemini with structured JSON mode
3. **Deterministic scoring** — Compliance calculated in Python, not by the LLM
4. **Defense in depth** — STT retries, LLM retries, enum clamping, global error handling
5. **Semantic audit trail** — ChromaDB indexes every call for pattern analysis

---

## 🤖 AI Tools Used

> **Disclosure as required by hackathon policy.**

| AI Tool | How It Was Used |
|---------|----------------|
| **Google Gemini 2.5 Flash** | Core LLM engine integrated into the application for call transcript analysis, SOP compliance detection, sentiment classification, and keyword extraction (`src/block_3_llm.py`) |
| **Sarvam AI** | Speech-to-Text engine integrated into the application for processing Hindi (Hinglish) and Tamil (Tanglish) audio recordings (`src/block_1_stt.py`) |
| **Claude (via Antigravity)** | Used as an AI pair-programming assistant throughout development — helped with architecture design, debugging API integrations, performance optimization (parallel STT processing), and building the frontend dashboard. All suggestions were reviewed, tested, and adapted to fit project requirements. |
| **Google Gemini (AI Assistant)** | Used for brainstorming solutions, troubleshooting deployment issues, and validating API response schemas during development. |

---

## ⚠️ Known Limitations

- **Sarvam Free Tier Rate Limits** — Parallel chunk processing may be throttled under heavy concurrent load on the free tier.
- **Audio Length** — Very long recordings (>10 minutes) may approach API timeout limits depending on network conditions.
- **Language Detection** — The system relies on the user-provided `language` field; it does not auto-detect the spoken language.
- **Gemini API Quota** — Response quality depends on Gemini API availability; the system includes retry logic but cannot guarantee uptime of third-party APIs.

---

*Built with ❤️ for HCL x Guvi Hackathon 2026*
