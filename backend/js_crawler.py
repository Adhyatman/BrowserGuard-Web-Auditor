from __future__ import annotations

import re
import threading
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

from config import REQUEST_TIMEOUT
from rate_limiter import rate_limit
import state


MAX_SNIPPET_LENGTH = 100

# ---------------- COMMENT REGEX ---------------- #

RE_SINGLE_COMMENT = re.compile(r"//.*")
RE_MULTI_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

COMMENT_CODE_PATTERNS = [
    re.compile(r"\bfunction\b"),
    re.compile(r"\b(var|let|const)\b"),
    re.compile(r"console\.(log|warn|error)"),
    re.compile(r"\bclass\b"),
    re.compile(r"\bif\b"),
    re.compile(r"\bfor\b"),
]

# ---------------- LINK REGEX ---------------- #

RE_JS_LINKS = re.compile(
    r"""["']([^"' ]+\.(?:html|php|jsp)|/[^"' ]+)["']""",
    re.IGNORECASE,
)

RE_ROUTE_PATTERNS = re.compile(
    r"""(?:navigate|router\.push|window\.location)[^\n]*["']([^"']+)["']""",
    re.IGNORECASE,
)


# ---------------- HELPERS ---------------- #

def _trim(text: str) -> str:
    """
    Create shortened preview text.
    """

    value = text.strip()

    if len(value) > MAX_SNIPPET_LENGTH:
        return value[:MAX_SNIPPET_LENGTH] + "..."

    return value


def _get_session():
    """
    Return shared requests session.
    """

    from crawler import get_session

    return get_session()


def _is_valid_js_link(link: str) -> bool:
    """
    Basic validation for extracted links.
    """

    if not link:
        return False

    link = link.strip().lower()

    if link.startswith((
        "javascript:",
        "mailto:",
        "tel:"
    )):
        return False

    if len(link) < 4:
        return False

    return True


def _fetch_js(url: str):
    """
    Download JavaScript file.
    """

    if state.STOP_EVENT.is_set():
        return None, None, "Stopped"

    try:

        rate_limit(url)

        session = _get_session()

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )

        if response.status_code >= 200 and response.status_code < 300:
            return response.text, response.status_code, ""

        return None, response.status_code, "Request failed"

    except Exception as error:
        return None, None, str(error)


def _looks_like_code(text: str) -> bool:
    """
    Check whether comment contains code.
    """

    for pattern in COMMENT_CODE_PATTERNS:

        if pattern.search(text):
            return True

    return False


# ---------------- COMMENT EXTRACTION ---------------- #

def _extract_comments(js_text: str):
    """
    Extract single-line and multi-line comments.
    """

    comments = []

    for match in RE_MULTI_COMMENT.finditer(js_text):
        comments.append(("multi", match.group(0)))

    for match in RE_SINGLE_COMMENT.finditer(js_text):
        comments.append(("single", match.group(0)))

    return comments


def detect_js_commented_code(
    js_text: str,
    js_url: str
):
    """
    Detect commented-out JavaScript code.
    """

    detections = []

    try:

        comments = _extract_comments(js_text)

        for comment_type, content in comments:

            if comment_type == "multi":
                inner = content[2:-2]
            else:
                inner = content[2:]

            if not inner.strip():
                continue

            if not _looks_like_code(inner):
                continue

            detections.append({
                "page_url": js_url,
                "type": "Commented Code (JS)",
                "element": "js_comment",
                "dom_snippet": _trim(content),
            })

    except Exception as error:
        print(f"[JS] Detection failed: {error}")

    return detections


# ---------------- LINK EXTRACTION ---------------- #

def extract_links_from_js(
    js_text: str,
    js_url: str
):
    """
    Extract possible page links from JS source.
    """

    found_links = []
    seen = set()

    raw_links = []

    for match in RE_JS_LINKS.finditer(js_text):
        raw_links.append(match.group(1))

    for match in RE_ROUTE_PATTERNS.finditer(js_text):
        raw_links.append(match.group(1))

    from link_extractor import normalise_url

    for item in raw_links:

        if not _is_valid_js_link(item):
            continue

        absolute_url = urljoin(js_url, item)

        normalised = normalise_url(
            absolute_url
        )

        if normalised in seen:
            continue

        seen.add(normalised)

        found_links.append(normalised)

    return found_links


# ---------------- MAIN CRAWLER ---------------- #

def crawl_js(
    js_url: str,
    base_domain: str,
    visited_js: set,
    comment_results: list,
    lock: threading.Lock,
    link_executor: ThreadPoolExecutor | None = None,
    visited_pages: set | None = None,
    queue=None,
    robots_rules=None,
    pagination_counts: dict | None = None,
):
    """
    Crawl and analyse JavaScript file.
    """

    if state.STOP_EVENT.is_set():
        return

    from link_extractor import (
        normalise_url,
        is_internal,
    )

    norm_js = normalise_url(js_url)

    with lock:

        if norm_js in visited_js:
            return

        visited_js.add(norm_js)

    js_text, status_code, error = _fetch_js(js_url)

    if js_text is None:

        if error != "Stopped":
            print(f"[JS] Failed to fetch: {js_url}")

        return

    if state.STOP_EVENT.is_set():
        return

    # Detect commented code
    detections = detect_js_commented_code(
        js_text,
        js_url
    )

    if detections:

        with lock:
            comment_results.extend(detections)

    # Extract JS links
    if visited_pages is not None and queue is not None:

        js_links = extract_links_from_js(
            js_text,
            js_url
        )

        if js_links:

            with lock:

                for link in js_links:

                    if state.STOP_EVENT.is_set():
                        break

                    if not is_internal(
                        link,
                        base_domain
                    ):
                        continue

                    normalised = normalise_url(link)

                    if normalised in visited_pages:
                        continue

                    visited_pages.add(normalised)

                    queue.append(
                        (normalised, js_url)
                    )

                    print(
                        f"[JS] Added URL from JS: {normalised}"
                    )