from __future__ import annotations

import re
from urllib.parse import urljoin
from concurrent.futures import as_completed

from config import REQUEST_TIMEOUT
from link_extractor import normalise_url, is_internal
from rate_limiter import rate_limit
import state


# Cache for delayed import
_check_link_status = None

MAX_CSS_DEPTH = 5
MAX_SNIPPET_SIZE = 100


# ---------------- SIMPLE REGEX ---------------- #

CSS_URL_PATTERN = re.compile(r'url\(["\']?([^"\')]+)')
CSS_IMPORT_PATTERN = re.compile(r'@import\s+["\']([^"\']+)')
CSS_COMMENT_PATTERN = re.compile(r'/\*.*?\*/', re.DOTALL)

COMMENT_CODE_PATTERNS = [
    re.compile(r"\{.*?\}"),
    re.compile(r":[^;]+;"),
    re.compile(r"@(media|import)", re.IGNORECASE),
]


# ---------------- HELPERS ---------------- #

def _trim(text: str) -> str:
    """
    Create short readable preview text.
    """
    value = text.strip()

    if len(value) > MAX_SNIPPET_SIZE:
        return value[:MAX_SNIPPET_SIZE] + "..."

    return value


def _get_session():
    """
    Load shared session object.
    """
    from crawler import get_session
    return get_session()


def _get_check_link_status():
    """
    Lazy import to avoid circular imports.
    """
    global _check_link_status

    if _check_link_status is None:
        from crawler import check_link_status
        _check_link_status = check_link_status

    return _check_link_status


def _fetch_css(url: str):
    """
    Download CSS content from URL.
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


# ---------------- CSS PARSING ---------------- #

def _extract_imports(css_text: str):
    """
    Find imported CSS files.
    """
    return CSS_IMPORT_PATTERN.findall(css_text)


def _strip_comments(css_text: str):
    """
    Remove CSS comments.
    """
    return CSS_COMMENT_PATTERN.sub("", css_text)


def _looks_like_code(text: str):
    """
    Detect whether comment contains code-like content.
    """
    for pattern in COMMENT_CODE_PATTERNS:
        if pattern.search(text):
            return True

    return False


def detect_css_commented_code(css_text: str, css_url: str):
    """
    Detect commented code blocks inside CSS.
    """

    detections = []

    for match in CSS_COMMENT_PATTERN.finditer(css_text):

        comment = match.group(0)

        # Remove comment markers
        inner_text = comment[2:-2]

        if not inner_text.strip():
            continue

        if not _looks_like_code(inner_text):
            continue

        detections.append({
            "page_url": css_url,
            "type": "Commented Code (CSS)",
            "element": "css_comment",
            "dom_snippet": _trim(comment),
        })

    return detections


# ---------------- RESOURCE CHECK ---------------- #

def _check_and_record(
    norm,
    source_url,
    base_domain,
    visited_resources,
    results,
    lock
):
    """
    Check asset URL and save result.
    """

    if state.STOP_EVENT.is_set():
        return

    check_link_status = _get_check_link_status()

    status, error = check_link_status(norm)

    external = not is_internal(norm, base_domain)

    entry = {
        "url": norm,
        "status_code": status,
        "error": error,
        "source": source_url,
        "link_type": "css_asset",
    }

    if external:
        entry["external"] = True

    with lock:
        results.append(entry)


def _enqueue_asset_checks(
    raw_urls,
    base_url,
    base_domain,
    visited_resources,
    results,
    lock,
    link_executor
):
    """
    Queue CSS asset checks.
    """

    if state.STOP_EVENT.is_set():
        return

    urls_to_check = []

    with lock:

        for raw in raw_urls:

            resolved = normalise_url(
                urljoin(base_url, raw)
            )

            if not resolved.startswith(("http://", "https://")):
                continue

            if resolved not in visited_resources:
                visited_resources.add(resolved)
                urls_to_check.append(resolved)

    futures = {
        link_executor.submit(
            _check_and_record,
            item,
            base_url,
            base_domain,
            visited_resources,
            results,
            lock
        ): item
        for item in urls_to_check
    }

    for future in as_completed(futures):
        try:
            future.result()
        except Exception:
            pass


# ---------------- MAIN CRAWLER ---------------- #

def crawl_css(
    css_url,
    base_domain,
    visited_css,
    visited_resources,
    results,
    comment_results,
    lock,
    link_executor,
    depth=0,
):
    """
    Crawl CSS files and extract linked assets.
    """

    if state.STOP_EVENT.is_set():
        return

    if depth > MAX_CSS_DEPTH:
        return

    normalised_css = normalise_url(css_url)

    with lock:

        if normalised_css in visited_css:
            return

        visited_css.add(normalised_css)

    css_text, status_code, error = _fetch_css(css_url)

    with lock:
        results.append({
            "url": normalised_css,
            "status_code": status_code,
            "error": error,
            "source": "css_crawler",
            "link_type": "css_file",
        })

    if css_text is None:
        return

    # Detect comments
    comments = detect_css_commented_code(
        css_text,
        css_url
    )

    if comments:
        with lock:
            comment_results.extend(comments)

    clean_css = _strip_comments(css_text)

    imports = _extract_imports(clean_css)

    asset_urls = CSS_URL_PATTERN.findall(clean_css)

    filtered_assets = []

    for item in asset_urls:

        item = item.strip()

        if not item:
            continue

        if item.startswith("data:"):
            continue

        filtered_assets.append(item)

    # Check assets
    if filtered_assets:
        _enqueue_asset_checks(
            filtered_assets,
            css_url,
            base_domain,
            visited_resources,
            results,
            lock,
            link_executor
        )

    # Stop before recursive calls
    if state.STOP_EVENT.is_set():
        return

    # Crawl imported CSS files
    for raw_import in imports:

        next_url = normalise_url(
            urljoin(css_url, raw_import)
        )

        if not next_url.startswith(("http://", "https://")):
            continue

        link_executor.submit(
            crawl_css,
            next_url,
            base_domain,
            visited_css,
            visited_resources,
            results,
            comment_results,
            lock,
            link_executor,
            depth + 1,
        )