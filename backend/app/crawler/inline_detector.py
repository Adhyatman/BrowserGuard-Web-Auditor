from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

MAX_SNIPPET_LENGTH = 100


def _trim(text: str) -> str:
    """
    Shorten long HTML snippets for cleaner output.
    """

    cleaned = text.strip()

    if len(cleaned) > MAX_SNIPPET_LENGTH:
        return cleaned[:MAX_SNIPPET_LENGTH] + "..."

    return cleaned


def _dom_snippet(tag) -> str:
    """
    Return a short preview of an HTML tag.
    """

    html = str(tag)

    end_index = html.find(">")

    if end_index == -1:
        return _trim(html)

    return _trim(html[: end_index + 1])


def _normalise_url(resource: str, page_url: str) -> str:
    """
    Convert relative URLs into absolute URLs.
    """

    return urljoin(page_url, resource.strip())


def _is_stylesheet_link(tag) -> bool:
    """
    Check whether a <link> tag is a CSS stylesheet.
    """

    rel = tag.get("rel", [])

    if isinstance(rel, str):
        rel = rel.split()

    rel = [item.lower() for item in rel]

    if "stylesheet" in rel:
        return True

    href = tag.get("href", "")

    if href:
        parsed = urlparse(href)

        if parsed.path.lower().endswith(".css"):
            return True

    return False


# ---------------- INLINE CSS ---------------- #

def _detect_inline_css(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Detect elements using style attributes.
    """

    detections = []

    for tag in soup.find_all(style=True):

        detections.append({
            "page_url": page_url,
            "type": "Inline CSS",
            "element": tag.name,
            "dom_snippet": _dom_snippet(tag),
        })

    return detections


# ---------------- INTERNAL CSS ---------------- #

def _detect_internal_css(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Detect CSS inside <style> tags.
    """

    detections = []

    for tag in soup.find_all("style"):

        css_code = tag.get_text()

        if not css_code.strip():
            continue

        preview = css_code[:80]

        detections.append({
            "page_url": page_url,
            "type": "Internal CSS",
            "element": "style",
            "dom_snippet": _trim(
                f"<style>{preview}</style>"
            ),
        })

    return detections


# ---------------- EXTERNAL CSS ---------------- #

def _detect_external_css(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Detect linked CSS files.
    """

    detections = []
    checked_urls = set()

    for tag in soup.find_all("link"):

        href = tag.get("href", "").strip()

        if not href:
            continue

        if not _is_stylesheet_link(tag):
            continue

        css_url = _normalise_url(
            href,
            page_url
        )

        if css_url in checked_urls:
            continue

        checked_urls.add(css_url)

        detections.append({
            "page_url": page_url,
            "type": "External CSS",
            "element": "link",
            "resource_url": css_url,
            "dom_snippet": _dom_snippet(tag),
        })

    return detections


# ---------------- INLINE JS ---------------- #

def _detect_inline_js(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Detect inline JavaScript blocks.
    """

    detections = []

    for tag in soup.find_all("script", src=False):

        js_code = tag.get_text()

        if not js_code.strip():
            continue

        detections.append({
            "page_url": page_url,
            "type": "Inline JS",
            "element": "script",
            "dom_snippet": _trim(
                f"<script>{js_code[:80]}</script>"
            ),
        })

    return detections


# ---------------- INLINE EVENTS ---------------- #

def _detect_inline_events(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Detect inline HTML event handlers.
    """

    detections = []

    for tag in soup.find_all(True):

        for attribute in tag.attrs:

            if attribute.lower().startswith("on"):

                detections.append({
                    "page_url": page_url,
                    "type": "Inline Event",
                    "element": tag.name,
                    "dom_snippet": _dom_snippet(tag),
                })

    return detections


# ---------------- EXTERNAL JS ---------------- #

def _detect_external_js(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Detect external JavaScript files.
    """

    detections = []
    checked_urls = set()

    for tag in soup.find_all("script", src=True):

        src = tag.get("src", "").strip()

        if not src:
            continue

        js_url = _normalise_url(
            src,
            page_url
        )

        if js_url in checked_urls:
            continue

        checked_urls.add(js_url)

        detections.append({
            "page_url": page_url,
            "type": "External JS",
            "element": "script",
            "resource_url": js_url,
            "dom_snippet": _dom_snippet(tag),
        })

    return detections


# ---------------- MAIN DETECTOR ---------------- #

def detect_inline_code(
    soup: BeautifulSoup,
    page_url: str
):
    """
    Run all inline code detectors.
    """

    detections = []

    detections.extend(
        _detect_inline_js(soup, page_url)
    )

    detections.extend(
        _detect_internal_css(soup, page_url)
    )

    detections.extend(
        _detect_inline_css(soup, page_url)
    )

    detections.extend(
        _detect_inline_events(soup, page_url)
    )

    detections.extend(
        _detect_external_css(soup, page_url)
    )

    detections.extend(
        _detect_external_js(soup, page_url)
    )

    return detections