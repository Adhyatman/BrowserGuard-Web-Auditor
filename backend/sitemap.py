import requests

from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT
from rate_limiter import rate_limit


def _get_session():
    """
    Load shared session object.
    """

    from crawler import get_session

    return get_session()


def fetch_sitemap_urls(
    sitemap_url: str,
    _visited: set[str] | None = None
):
    """
    Fetch sitemap URLs recursively.

    Supports:
    - sitemap index files
    - regular sitemap files
    """

    if _visited is None:
        _visited = set()

    # Prevent duplicate sitemap crawling
    if sitemap_url in _visited:
        return []

    _visited.add(sitemap_url)

    collected_urls = []

    try:

        rate_limit(sitemap_url)

        session = _get_session()

        response = session.get(
            sitemap_url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:

            print(
                f"[SITEMAP] Failed to fetch "
                f"{sitemap_url}"
            )

            return collected_urls

        soup = BeautifulSoup(
            response.content,
            "xml"
        )

        # Sitemap index
        if soup.find("sitemapindex"):

            for tag in soup.find_all("loc"):

                child_sitemap = tag.get_text(
                    strip=True
                )

                if not child_sitemap:
                    continue

                child_urls = fetch_sitemap_urls(
                    child_sitemap,
                    _visited
                )

                collected_urls.extend(child_urls)

        # Regular sitemap
        else:

            for tag in soup.find_all("loc"):

                page_url = tag.get_text(
                    strip=True
                )

                if not page_url:
                    continue

                collected_urls.append(page_url)

    except requests.exceptions.RequestException as error:

        print(
            f"[SITEMAP] Request error: {error}"
        )

    return collected_urls