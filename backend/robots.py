import requests

from urllib.parse import urlparse

from config import REQUEST_TIMEOUT
from rate_limiter import rate_limit


def _get_session():
    """
    Load shared requests session lazily.
    """

    from crawler import get_session

    return get_session()


# ---------------- RULE STORAGE ---------------- #

class _RobotsRules:
    """
    Store parsed robots.txt rules.
    """

    __slots__ = ("_rules",)

    def __init__(self, rules):

        self._rules = rules

    def is_allowed(self, path: str) -> bool:
        """
        Check whether path is allowed.
        """

        if not self._rules:
            return True

        best_match_length = -1
        best_result = True

        for rule_path, allow in self._rules:

            if _matches(path, rule_path):

                current_length = len(rule_path)

                if current_length > best_match_length:
                    best_match_length = current_length
                    best_result = allow

        return best_result


# ---------------- MATCH HELPERS ---------------- #

def _matches(path: str, rule: str) -> bool:
    """
    Basic robots.txt path matching.
    """

    # Simple prefix check
    if "*" not in rule and not rule.endswith("$"):
        return path.startswith(rule)

    # Convert wildcard logic manually
    end_anchor = rule.endswith("$")

    clean_rule = rule.rstrip("$")

    parts = clean_rule.split("*")

    current_position = 0

    for part in parts:

        if not part:
            continue

        index = path.find(part, current_position)

        if index == -1:
            return False

        current_position = index + len(part)

    if end_anchor:
        return current_position == len(path)

    return True


# ---------------- FETCH ROBOTS ---------------- #

def fetch_robots_rules(
    base_domain: str,
    scheme: str
):
    """
    Download and parse robots.txt.
    """

    robots_url = f"{scheme}://{base_domain}/robots.txt"

    rules = []
    sitemap_urls = []

    try:

        rate_limit(robots_url)

        session = _get_session()

        response = session.get(
            robots_url,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )

        if response.status_code != 200:

            print(
                f"[ROBOTS] robots.txt not found: {robots_url}"
            )

            return _RobotsRules([]), sitemap_urls

        inside_wildcard = False

        for raw_line in response.text.splitlines():

            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            lower = line.lower()

            # User-agent section
            if lower.startswith("user-agent:"):

                agent = line.split(":", 1)[1].strip()

                inside_wildcard = (
                    agent == "*"
                )

                continue

            # Parse rules
            if inside_wildcard:

                if lower.startswith("disallow:"):

                    path = line.split(
                        ":",
                        1
                    )[1].strip()

                    if path:
                        rules.append(
                            (path, False)
                        )

                    continue

                if lower.startswith("allow:"):

                    path = line.split(
                        ":",
                        1
                    )[1].strip()

                    if path:
                        rules.append(
                            (path, True)
                        )

                    continue

            # Sitemap
            if lower.startswith("sitemap:"):

                sitemap = line.split(
                    ":",
                    1
                )[1].strip()

                if sitemap:
                    sitemap_urls.append(sitemap)

        print(
            f"[ROBOTS] Loaded {len(rules)} rule(s)"
        )

    except requests.exceptions.RequestException as error:

        print(
            f"[ROBOTS] Failed to fetch robots.txt: {error}"
        )

    return _RobotsRules(rules), sitemap_urls


# ---------------- PUBLIC CHECK ---------------- #

def is_allowed_by_robots(
    url: str,
    robots_rules: _RobotsRules
):
    """
    Check whether URL is allowed by robots.txt.
    """

    if robots_rules is None:
        return True

    parsed = urlparse(url)

    path = parsed.path or "/"

    return robots_rules.is_allowed(path)