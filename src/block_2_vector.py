"""
block_2_vector.py — ChromaDB Semantic Audit Store
Stores processed call transcripts with metadata for searchable analytics.
Uses HuggingFace multilingual embeddings for semantic indexing.

Design Decision: ChromaDB serves as a persistent semantic audit store —
every processed call is indexed with compliance metadata for searchable
analytics across all historical calls. This is NOT used for retrieval
during analysis (SOP compliance is a classification problem, not retrieval).
"""

import os
import tempfile
import hashlib
from datetime import datetime

import chromadb
from chromadb.utils import embedding_functions

# ═══════════════════════════════════════════════════════════════════════════
#  Module-level initialization — loads ONCE at server startup, not per request
# ═══════════════════════════════════════════════════════════════════════════

print("[VectorDB] Loading HuggingFace multilingual embedding model (one-time)...")

# Multilingual model that handles Tamil, Hindi, and English in a single vector space
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)

# ── Persistent ChromaDB client — data survives server restarts ──────────
# Uses CHROMA_PERSIST_DIR env var, defaults to system temp directory
_chroma_persist_dir = os.getenv(
    "CHROMA_PERSIST_DIR",
    os.path.join(tempfile.gettempdir(), "call_analytics_chroma")
)

try:
    _chroma_client = chromadb.PersistentClient(path=_chroma_persist_dir)
    print(f"[VectorDB] Using persistent storage at: {_chroma_persist_dir}")
except Exception as e:
    print(f"[VectorDB] WARNING: Persistent storage failed ({e}), using in-memory fallback")
    _chroma_client = chromadb.Client()

# Collection for storing all processed call transcripts as audit trail
_audit_collection = _chroma_client.get_or_create_collection(
    name="call_audit_store",
    embedding_function=_embedding_fn,
    metadata={"description": "Semantic audit store for all processed call transcripts"}
)

print(f"[VectorDB] Ready! Existing calls in audit store: {_audit_collection.count()}")


# ═══════════════════════════════════════════════════════════════════════════
#  Store a processed call transcript with metadata (audit trail)
# ═══════════════════════════════════════════════════════════════════════════

def store_call_transcript(transcript: str, language: str, compliance_score: float,
                          payment_preference: str, sentiment: str) -> str:
    """
    Stores a processed call transcript in ChromaDB with rich metadata.
    Creates a searchable semantic audit trail of all processed calls.

    Args:
        transcript: Full call transcript text
        language: Language of the call (Tamil, Hindi, etc.)
        compliance_score: SOP compliance score (0.0 to 1.0)
        payment_preference: Classified payment type
        sentiment: Call sentiment (Positive/Neutral/Negative)

    Returns:
        The document ID used for storage
    """
    # Generate unique ID from transcript content + timestamp
    hash_input = f"{transcript}_{datetime.now().isoformat()}"
    doc_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]

    try:
        _audit_collection.upsert(
            documents=[transcript],
            ids=[doc_id],
            metadatas=[{
                "language": language,
                "compliance_score": compliance_score,
                "payment_preference": payment_preference,
                "sentiment": sentiment,
                "processed_at": datetime.now().isoformat(),
            }]
        )
        print(f"[VectorDB] Stored call (ID: {doc_id}), "
              f"total in store: {_audit_collection.count()}")
    except Exception as e:
        print(f"[VectorDB] WARNING: Failed to store — {str(e)}")

    return doc_id


# ═══════════════════════════════════════════════════════════════════════════
#  Search audit store (semantic queries across historical calls)
# ═══════════════════════════════════════════════════════════════════════════

def search_audit_store(query: str, n_results: int = 5) -> list:
    """
    Searches the semantic audit store for similar call transcripts.
    Useful for finding patterns across historical calls.

    Args:
        query: Natural language search query
        n_results: Maximum number of results to return

    Returns:
        List of matching transcript strings
    """
    try:
        count = _audit_collection.count()
        if count == 0:
            return []

        results = _audit_collection.query(
            query_texts=[query],
            n_results=min(n_results, count)
        )
        documents = results.get("documents", [[]])[0]
        print(f"[VectorDB] Found {len(documents)} matches for: '{query[:50]}...'")
        return documents
    except Exception as e:
        print(f"[VectorDB] Search error: {str(e)}")
        return []


def get_audit_stats() -> dict:
    """Returns statistics about the semantic audit store."""
    try:
        count = _audit_collection.count()
        return {
            "status": "ok",
            "total_calls_stored": count,
            "collection": "call_audit_store",
            "persist_directory": _chroma_persist_dir,
        }
    except Exception:
        return {
            "status": "ok",
            "total_calls_stored": 0,
            "collection": "call_audit_store",
        }
