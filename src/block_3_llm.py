"""
block_3_llm.py — LLM Analysis using Google Gemini
Generates structured JSON for call compliance analysis.
Uses Gemini's JSON mode for guaranteed valid JSON output.
"""

import json
import os
import time
from google import genai
from google.genai import types

# ═══════════════════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════════════════

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))  # 0 = disabled for speed
GEMINI_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "120000"))  # 2 minutes
MAX_RETRIES = 3

# ── Initialize Gemini client with timeout ────────────────────────────────
_api_key = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(
    api_key=_api_key,
    http_options={"timeout": GEMINI_TIMEOUT_MS},
)

if not _api_key:
    print("[LLM] WARNING: GEMINI_API_KEY is not set!")
else:
    print(f"[LLM] Gemini client initialized (model: {MODEL_NAME}, "
          f"timeout: {GEMINI_TIMEOUT_MS}ms)")


# ═══════════════════════════════════════════════════════════════════════════
#  Prompt Template — optimized for accurate SOP detection & classification
# ═══════════════════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """You are an expert Call Center Quality Assurance AI specialized in analyzing Indian call center conversations in Hinglish (Hindi-English mix) and Tanglish (Tamil-English mix).

Analyze the following call center transcript carefully.

## SOP (Standard Operating Procedure) Validation Rules

Determine whether EACH of these five steps was followed by the agent:

1. **greeting**: Did the agent greet the customer at the start of the call?
   Evidence to look for: "Hello", "Hi", "Vanakkam", "Namaste", "Good morning/afternoon/evening", or any welcoming phrase.
   → Set TRUE if ANY form of greeting is found at or near the start of the call.

2. **identification**: Did the agent identify themselves (stated their name, company, or department) OR verify/confirm the customer's identity (asked or confirmed the customer's name)?
   Evidence: "I am calling from [company]", "Am I speaking with [name]?", "This is [name] from [company]", addressing customer by name.
   → Set TRUE if the agent stated who they are OR confirmed who the customer is.

3. **problemStatement**: Did the agent clearly explain the PURPOSE or reason for the call?
   Evidence: explaining an outstanding payment, describing a course inquiry follow-up, stating what the call is about, presenting an offer or issue.
   → Set TRUE if the reason for the call was communicated clearly.

4. **solutionOffering**: Did the agent offer any solution, product, plan, recommendation, or actionable next steps?
   Evidence: offering EMI plans, course details, payment options, discounts, scheduling follow-ups, sending information via WhatsApp/email.
   → Set TRUE if any solution, product, or next step was offered.

5. **closing**: Did the agent properly close/end the call with a farewell?
   Evidence: "Thank you", "Thanks", "Okay bye", "Have a good day", confirming next steps before ending, "I'll send the details".
   → Set TRUE if there is a proper ending/farewell at the close of the call.

IMPORTANT: Set each to TRUE only if you find clear evidence in the transcript. Set to FALSE if the step is missing or unclear.

## Analytics Classification Rules

Classify using ONLY these exact values:

- **paymentPreference**: What payment method was discussed or preferred by the customer?
  Must be EXACTLY one of: "EMI", "FULL_PAYMENT", "PARTIAL_PAYMENT", "DOWN_PAYMENT"
  - EMI: Monthly installments or EMI plans discussed
  - FULL_PAYMENT: Customer agrees or discusses paying the full amount at once
  - PARTIAL_PAYMENT: Customer offers to pay part now and the rest later
  - DOWN_PAYMENT: Customer discusses paying an initial/advance amount to start

- **rejectionReason**: If the customer did NOT agree, hesitated, or deferred the decision, what was the reason?
  Must be EXACTLY one of: "HIGH_INTEREST", "BUDGET_CONSTRAINTS", "ALREADY_PAID", "NOT_INTERESTED", "NONE"
  - HIGH_INTEREST: Customer objects to high interest rates or charges
  - BUDGET_CONSTRAINTS: Customer says they can't afford it, need to check finances, or will consult family about budget
  - ALREADY_PAID: Customer claims they've already made the payment
  - NOT_INTERESTED: Customer explicitly says they're not interested
  - NONE: Customer agreed to proceed or no clear rejection occurred

- **sentiment**: Overall tone of the conversation.
  Must be EXACTLY one of: "Positive", "Neutral", "Negative"

## Summary
Write a concise 2-3 sentence summary capturing: who called whom, the main topic discussed, key details mentioned, and the outcome or decision reached.

## Keywords
Extract 5-10 important keywords or key phrases that APPEAR IN or are DIRECTLY TRACEABLE to the transcript content. Include: names of people, organizations, products/courses, payment terms, amounts, and key discussion topics.

## TRANSCRIPT TO ANALYZE:
{transcript}

Return the analysis as JSON with this exact structure:
{{
  "summary": "concise 2-3 sentence summary",
  "sop_validation": {{
    "greeting": true or false,
    "identification": true or false,
    "problemStatement": true or false,
    "solutionOffering": true or false,
    "closing": true or false,
    "explanation": "Brief explanation of which SOP steps were present or missing and why"
  }},
  "analytics": {{
    "paymentPreference": "EMI or FULL_PAYMENT or PARTIAL_PAYMENT or DOWN_PAYMENT",
    "rejectionReason": "HIGH_INTEREST or BUDGET_CONSTRAINTS or ALREADY_PAID or NOT_INTERESTED or NONE",
    "sentiment": "Positive or Neutral or Negative"
  }},
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}"""


# ═══════════════════════════════════════════════════════════════════════════
#  LLM Call with JSON Mode + Retry Logic
# ═══════════════════════════════════════════════════════════════════════════

def call_llm_for_final_json(transcript_text: str) -> dict:
    """
    Sends the full transcript to Gemini for structured compliance analysis.
    Uses Gemini's JSON response mode for guaranteed valid JSON output.

    Args:
        transcript_text: The full call transcript from STT

    Returns:
        Dictionary with summary, sop_validation, analytics, and keywords
    """
    print(f"[LLM] Analyzing transcript ({len(transcript_text)} chars) with {MODEL_NAME}...")

    prompt = ANALYSIS_PROMPT.format(transcript=transcript_text)

    # ── Gemini config: JSON mode + low temperature for consistent classification ──
    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",  # Forces valid JSON output
        temperature=0.1,  # Low temp for deterministic classification
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=gen_config,
            )

            raw_text = response.text.strip()

            # ── Safety: strip markdown wrapping if present despite JSON mode ──
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            # Parse JSON
            result = json.loads(raw_text)
            print("[LLM] Successfully parsed structured JSON from Gemini.")
            return result

        except json.JSONDecodeError as e:
            print(f"[LLM] JSON parse error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            print(f"[LLM] Raw response: {raw_text[:300]}...")

        except Exception as e:
            print(f"[LLM] Error (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")

        # Wait before retry with exponential backoff
        if attempt < MAX_RETRIES - 1:
            wait_time = 2 ** (attempt + 1)
            print(f"[LLM] Retrying in {wait_time}s...")
            time.sleep(wait_time)

    # ── Fallback: return safe defaults so the API NEVER crashes ─────────
    print("[LLM] All attempts failed. Returning safe fallback response.")
    return {
        "summary": "Call analysis could not be completed due to a processing error.",
        "sop_validation": {
            "greeting": False,
            "identification": False,
            "problemStatement": False,
            "solutionOffering": False,
            "closing": False,
            "explanation": "LLM analysis was unavailable — defaulting all SOP steps to not detected."
        },
        "analytics": {
            "paymentPreference": "FULL_PAYMENT",
            "rejectionReason": "NONE",
            "sentiment": "Neutral"
        },
        "keywords": []
    }
