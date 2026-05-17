"""
ai_analyzer.py - Groq AI analysis layer (additive, zero impact on crawl logic).

Usage:
    from app.ai_analyzer import analyze_with_ai
    ai_insights = analyze_with_ai(crawl_result)
"""

import os
import json
import logging
from collections import Counter
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AI_TIMEOUT_SECONDS = 30
AI_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

MAX_PROMPT_CHARS = 12000  # prevents token explosion / prompt injection abuse


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _safe_json(obj) -> str:
    """Safely serialize and truncate LLM input."""
    try:
        return json.dumps(obj, ensure_ascii=False)[:MAX_PROMPT_CHARS]
    except Exception:
        return "{}"


def _aggregate(crawl_result: dict) -> dict:
    """
    Distil crawl output into a compact, model-friendly structure.
    """

    summary = crawl_result.get("summary", {}) or {}
    results = crawl_result.get("results", []) or []
    inline_results = crawl_result.get("inline_results", []) or []
    comment_results = crawl_result.get("comment_results", []) or []

    # ---------------- Broken links ----------------
    broken = [r for r in results if r.get("classification") == "BROKEN"]

    source_counter = Counter(
        r.get("source", "").strip()
        for r in broken
        if r.get("source")
    )

    top_pages = [
        {"url": url, "count": cnt}
        for url, cnt in source_counter.most_common(5)
    ]

    # Better URL grouping (domain-aware)
    pattern_counter = Counter()
    for r in broken:
        url = r.get("url", "")
        try:
            parsed = urlparse(url)
            parts = parsed.path.strip("/").split("/")
            pattern = f"{parsed.netloc}/" + (parts[0] if parts and parts[0] else "")
        except Exception:
            pattern = "/"
        pattern_counter[pattern] += 1

    top_patterns = [p for p, _ in pattern_counter.most_common(3)]

    broken_links_detail = {
        "total": len(broken),
        "top_pages": top_pages,
        "top_patterns": top_patterns,
    }

    # ---------------- Inline / comment breakdown ----------------
    inline_types = Counter(
        r.get("type") if isinstance(r, dict) else "unknown"
        for r in inline_results
    )

    comment_types = Counter(
        r.get("type") if isinstance(r, dict) else "unknown"
        for r in comment_results
    )

    return {
        "total_pages": summary.get("unique", 0),
        "broken_links": summary.get("broken", 0),
        "redirects": summary.get("redirects", 0),
        "forbidden": summary.get("forbidden", 0),
        "server_errors": summary.get("server_errors", 0),

        "inline_css": inline_types.get("Inline CSS", 0),
        "external_css": inline_types.get("External CSS", 0),
        "inline_js": inline_types.get("Inline JS", 0),
        "external_js": inline_types.get("External JS", 0),

        "commented_code": sum(comment_types.values()),
        "broken_links_detail": broken_links_detail,
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """You are a senior web performance and SEO engineer.

Analyze the following website audit summary and provide structured insights.

DATA:
{data}

Return format:

1. PRIORITY FIXES (Top 5)
- Issue
- Why it matters
- Impact (High/Medium/Low)

2. ROOT CAUSE ANALYSIS
- Patterns and systemic issues

3. ACTIONABLE FIXES
- Concrete developer steps

Rules:
- Be concise
- Do NOT repeat raw data
- Focus on engineering insights
"""


def _build_prompt(aggregated: dict) -> str:
    safe_data = _safe_json(aggregated)
    return _PROMPT_TEMPLATE.format(data=safe_data)


# ---------------------------------------------------------------------------
# Groq call
# ---------------------------------------------------------------------------

def analyze_with_ai(crawl_result: dict) -> dict:
    """
    Runs AI analysis on crawl summary.
    """

    try:
        from groq import Groq
    except ImportError:
        logger.warning("groq package not installed; skipping AI analysis.")
        return {"ai_error": "groq package not installed"}

    api_key = os.environ.get("GROQ_API_KEY", "").strip()

    if not api_key:
        logger.warning("GROQ_API_KEY not set; skipping AI analysis.")
        return {"ai_error": "GROQ_API_KEY not set"}

    aggregated = _aggregate(crawl_result)
    prompt = _build_prompt(aggregated)

    try:
        client = Groq(api_key=api_key)

        completion = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )

        text = completion.choices[0].message.content

        return {"ai_insights": text}

    except Exception as exc:
        logger.exception("Groq AI call failed")
        return {"ai_error": f"AI analysis unavailable: {str(exc)}"}