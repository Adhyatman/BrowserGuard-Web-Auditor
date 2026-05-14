from bs4 import BeautifulSoup
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    urlencode,
)

from config import (
    NON_HTML_EXTENSIONS,
    IGNORED_QUERY_PARAMS,
    PAGINATION_PARAMS,
    MAX_PAGINATION_DEPTH,
)


# ---------------- URL HELPERS ---------------- #

def is_internal(
    url: str,
    base_domain: str
):
    """
    Check whether a URL belongs to the same domain.
    """

    parsed = urlparse(url)

    return (
        parsed.netloc == base_domain
        or parsed.netloc == ""
    )


def normalise_url(url: str) -> str:
    """
    Clean and normalize URLs for deduplication.
    """

    parsed = urlparse(url)

    clean_path = parsed.path.rstrip("/")

    if not clean_path:
        clean_path = "/"

    clean_query = ""

    if parsed.query:

        params = parse_qs(
            parsed.query,
            keep_blank_values=True
        )

        filtered = {}

        for key, value in params.items():

            if key.lower() in IGNORED_QUERY_PARAMS:
                continue

            filtered[key] = value

        clean_query = urlencode(
            sorted(filtered.items()),
            doseq=True
        )

    cleaned = parsed._replace(
        path=clean_path,
        query=clean_query,
        fragment=""
    )

    return cleaned.geturl()


def is_non_html_resource(url: str) -> bool:
    """
    Detect whether URL points to non-HTML file.
    """

    path = urlparse(url).path.lower()

    filename = path.split("/")[-1]

    if "." not in filename:
        return False

    extension = "." + filename.split(".")[-1]

    return extension in NON_HTML_EXTENSIONS


# ---------------- LINK EXTRACTION ---------------- #

def _extract_from_tags(
    soup: BeautifulSoup,
    page_url: str,
    base_domain: str
):
    """
    Extract internal, external, and resource links.
    """

    crawlable = []
    resources = []
    external = []

    internal_urls = []
    external_urls = []

    for tag in soup.find_all(True):

        for attribute in ("href", "src"):

            value = tag.get(attribute, "").strip()

            if not value:
                continue

            if value.startswith((
                "mailto:",
                "javascript:",
                "tel:",
                "#"
            )):
                continue

            absolute_url = normalise_url(
                urljoin(page_url, value)
            )

            if not absolute_url.startswith((
                "http://",
                "https://"
            )):
                continue

            if is_internal(
                absolute_url,
                base_domain
            ):
                internal_urls.append(absolute_url)
            else:
                external_urls.append(absolute_url)

    # Remove duplicates from internal links
    seen_internal = set()

    for url in internal_urls:

        if url in seen_internal:
            continue

        seen_internal.add(url)

        if is_non_html_resource(url):
            resources.append(url)
        else:
            crawlable.append(url)

    # Remove duplicates from external links
    seen_external = set()

    for url in external_urls:

        if url in seen_external:
            continue

        seen_external.add(url)

        external.append(url)

    return crawlable, resources, external


def extract_links_from_soup(
    soup: BeautifulSoup,
    page_url: str,
    base_domain: str
):
    """
    Extract links directly from BeautifulSoup object.
    """

    return _extract_from_tags(
        soup,
        page_url,
        base_domain
    )


def extract_links(
    html: str,
    page_url: str,
    base_domain: str
):
    """
    Parse HTML and extract links.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    return _extract_from_tags(
        soup,
        page_url,
        base_domain
    )


# ---------------- PAGINATION HELPERS ---------------- #

def pagination_series_key(url: str):
    """
    Create stable key for paginated URLs.
    """

    parsed = urlparse(url)

    if not parsed.query:
        return None

    params = parse_qs(
        parsed.query,
        keep_blank_values=True
    )

    pagination_keys = set()

    for key in params:

        if key.lower() in PAGINATION_PARAMS:
            pagination_keys.add(key)

    if not pagination_keys:
        return None

    remaining = {}

    for key, value in params.items():

        if key.lower() in PAGINATION_PARAMS:
            continue

        remaining[key] = value

    stable_query = urlencode(
        sorted(remaining.items()),
        doseq=True
    )

    base_url = parsed._replace(
        query=stable_query,
        fragment=""
    ).geturl()

    return base_url


def is_pagination_allowed(
    url: str,
    pagination_counts: dict
):
    """
    Limit excessive pagination crawling.
    """

    key = pagination_series_key(url)

    if key is None:
        return True

    current_count = pagination_counts.get(
        key,
        0
    )

    if current_count >= MAX_PAGINATION_DEPTH:
        return False

    pagination_counts[key] = current_count + 1

    return True