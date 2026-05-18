import re
from bs4 import BeautifulSoup, Comment

# Maximum length for preview text
MAX_PREVIEW_LENGTH = 100

# Simple patterns used to identify possible code inside comments
COMMENT_CODE_PATTERNS = [
    re.compile(r"<[a-zA-Z]+"),                 # HTML tags
    re.compile(r"</[a-zA-Z]+>"),               # Closing HTML tags
    re.compile(r"\bfunction\b"),               # JavaScript function keyword
    re.compile(r"\b(var|let|const)\b"),        # JavaScript variables
    re.compile(r"console\.(log|error|warn)"),  # Console methods
    re.compile(r"\$\("),                       # jQuery style syntax
    re.compile(r"[a-zA-Z-]+\s*:\s*.*;"),       # CSS property syntax
]


def _trim(text: str) -> str:
    """
    Reduce long text into a short readable preview.
    """
    cleaned = text.strip()

    if len(cleaned) > MAX_PREVIEW_LENGTH:
        return cleaned[:MAX_PREVIEW_LENGTH] + "..."

    return cleaned


def _looks_like_code(text: str) -> bool:
    """
    Check whether a comment contains code-like patterns.
    """
    for pattern in COMMENT_CODE_PATTERNS:
        if pattern.search(text):
            return True

    return False


def detect_commented_code(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """
    Scan HTML comments and detect comments that may contain code.

    Args:
        soup: BeautifulSoup object
        page_url: URL of scanned page

    Returns:
        List of detected comment issues
    """

    detections = []

    # Find all HTML comments
    comments = soup.find_all(
        string=lambda item: isinstance(item, Comment)
    )

    for comment in comments:

        comment_text = str(comment).strip()

        # Skip empty comments
        if not comment_text:
            continue

        # Check whether comment contains possible code
        if not _looks_like_code(comment_text):
            continue

        # Create simplified preview
        dom_preview = _trim(f"<!-- {comment_text} -->")

        # Store detection result
        detections.append({
            "page_url": page_url,
            "type": "Commented Code",
            "element": "comment",
            "dom_snippet": dom_preview,
        })

    return detections