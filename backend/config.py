REQUEST_TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BrokenLinkChecker/1.0)"
}

STATUS_REDIRECT = (301, 302, 303, 307, 308)
STATUS_BROKEN_MIN = 400
MAX_PAGES = 10000

NON_HTML_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".css", ".js",
    ".pdf", ".zip",
    ".mp4", ".mp3",
    ".woff", ".woff2", ".ttf", ".eot", ".ico",
    ".oembed",
    ".xml",
    ".json"
}

IGNORED_QUERY_PARAMS = {
    # Analytics / tracking
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_referrer",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "msclkid", "ttclid", "twclid", "li_fat_id", "mc_cid", "mc_eid",
    # Session / auth noise
    "session", "sessionid", "sid", "token", "csrf",
    # Referral / source noise
    "ref", "referrer", "source", "src", "affiliate",
    # Cache busting / timestamps
    "v", "ver", "version", "ts", "t", "cb", "cachebust",
    # Social share noise
    "share", "shared",
}

MAX_WORKERS = 8
REQUEST_DELAY = 0.3
MAX_RETRIES = 3

JS_RENDER_TIMEOUT = 30000
JS_SETTLE_MS      = 2000   # extra ms to let JS frameworks commit DOM changes after networkidle
JS_RENDER_DEBUG   = False  # set True temporarily to print rendered HTML snippets for debugging

PAGINATION_PARAMS = {"page", "p", "pg", "paged", "offset", "start", "from"}
MAX_PAGINATION_DEPTH = 8