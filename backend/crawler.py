import sys
import time
import threading
import requests
from urllib.parse import urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

from config import (
    REQUEST_TIMEOUT, HEADERS, STATUS_REDIRECT,
    MAX_PAGES, MAX_WORKERS, MAX_RETRIES
)

from rate_limiter import rate_limit
from link_extractor import (
    extract_links_from_soup,
    normalise_url,
    is_internal,
    is_non_html_resource,
    is_pagination_allowed
)

from inline_detector import detect_inline_code
from comment_detector import detect_commented_code
from css_crawler import crawl_css
from js_crawler import crawl_js
from robots import fetch_robots_rules, is_allowed_by_robots
from sitemap import fetch_sitemap_urls
from html_fetcher import fetch_html

import state

_thread_local = threading.local()

# simple global caches
_css_seen = set()
_js_seen = set()


# ---------------- SESSION ---------------- #

def get_session():
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update(HEADERS)
        _thread_local.session = s
    return _thread_local.session


# ---------------- STATUS ---------------- #

def _status_type(code, error, external=False):
    if error:
        return "ERROR"
    if code and 200 <= code < 300:
        return "OK"
    if code == 404:
        return "NOT_FOUND"
    if code == 403:
        return "BLOCKED"
    if code and 500 <= code < 600:
        return "SERVER_ERROR"
    return "OTHER"


# ---------------- LINK CHECK ---------------- #

def check_link_status(url):
    try:
        rate_limit(url)
        res = get_session().head(url, timeout=REQUEST_TIMEOUT)

        if res.status_code == 405:
            res = get_session().get(url, timeout=REQUEST_TIMEOUT)

        return res.status_code, ""

    except Exception as e:
        return None, str(e)


def _check_one(url, source, is_external):
    code, err = check_link_status(url)

    return {
        "url": url,
        "status_code": code,
        "classification": _status_type(code, err, is_external),
        "error": err,
        "source": source,
        "link_type": "external" if is_external else "resource"
    }


# ---------------- PARALLEL CHECK ---------------- #

def _check_batch(urls, visited, results, source, is_external, lock, executor):
    if state.STOP_EVENT.is_set():
        return

    to_process = []

    with lock:
        for u in urls:
            n = normalise_url(u)
            if n not in visited:
                visited.add(n)
                to_process.append(n)

    futures = [executor.submit(_check_one, u, source, is_external) for u in to_process]

    for f in as_completed(futures):
        results.append(f.result())


# ---------------- CRAWL PAGE ---------------- #

def crawl_page(url, base_domain, visited_pages, visited_resources,
               visited_external, results, queue, source=None,
               lock=None, robots_rules=None,
               inline_results=None, comment_results=None,
               pagination_counts=None, executor=None, js_render=False):

    lock = lock or threading.Lock()

    if state.STOP_EVENT.is_set():
        return

    html, code, err = fetch_html(url, js_render, get_session())

    results.append({
        "url": url,
        "status_code": code,
        "classification": _status_type(code, err),
        "error": err,
        "source": source,
        "link_type": "page"
    })

    if not html or not (code and 200 <= code < 300):
        return

    soup = BeautifulSoup(html, "html.parser")

    crawl_links, resource_links, external_links = extract_links_from_soup(
        soup, url, base_domain
    )

    # ---------------- INLINE DETECTION ---------------- #

    if inline_results is not None:
        inline = detect_inline_code(soup, url)
        inline_results.extend(inline)

        comments = detect_commented_code(soup, url)
        if comment_results is not None:
            comment_results.extend(comments)

    # ---------------- QUEUE LINKS ---------------- #

    with lock:
        for link in crawl_links:
            if state.STOP_EVENT.is_set():
                break

            n = normalise_url(link)

            if n in visited_pages:
                continue

            if robots_rules and not is_allowed_by_robots(n, robots_rules):
                continue

            if not is_pagination_allowed(n, pagination_counts or {}):
                continue

            visited_pages.add(n)
            queue.append((n, url))

    # ---------------- RESOURCE CHECKS ---------------- #

    if executor:
        _check_batch(resource_links, visited_resources, results, url, False, lock, executor)
        _check_batch(external_links, visited_external, results, url, True, lock, executor)


# ---------------- EXECUTOR ---------------- #

def _run(queue, visited_pages, visited_resources, visited_external,
         results, lock, robots_rules,
         inline_results, comment_results,
         base_domain, pagination_counts,
         js_render=False):

    workers = 2 if js_render else MAX_WORKERS

    with ThreadPoolExecutor(max_workers=workers) as executor:

        def submit():
            with lock:
                while queue and len(visited_pages) < MAX_PAGES:
                    url, src = queue.popleft()
                    executor.submit(
                        crawl_page,
                        url, base_domain,
                        visited_pages,
                        visited_resources,
                        visited_external,
                        results,
                        queue,
                        src,
                        lock,
                        robots_rules,
                        inline_results,
                        comment_results,
                        pagination_counts,
                        executor,
                        js_render
                    )

        submit()


# ---------------- QUEUE BUILDER ---------------- #

def _build_queue(start_url, base_domain, robots_rules, sitemap_urls):
    q = deque()
    visited = set()

    start = normalise_url(start_url)
    q.append((start, None))
    visited.add(start)

    for sm in sitemap_urls:
        for url in fetch_sitemap_urls(sm):
            n = normalise_url(url)

            if (
                is_internal(n, base_domain)
                and n not in visited
                and not is_non_html_resource(n)
                and is_allowed_by_robots(n, robots_rules)
            ):
                visited.add(n)
                q.append((n, "sitemap"))

    return q, visited


# ---------------- API ENTRY ---------------- #

def run_checker_api(start_url: str, js_render=False, job_id=None):

    parsed = urlparse(start_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL")

    base_domain = parsed.netloc

    robots, sitemaps = fetch_robots_rules(base_domain, parsed.scheme)
    queue, visited_pages = _build_queue(start_url, base_domain, robots, sitemaps)

    results = []
    inline_results = []
    comment_results = []
    pagination_counts = {}

    lock = threading.Lock()

    _run(
        queue,
        visited_pages,
        set(),
        set(),
        results,
        lock,
        robots,
        inline_results,
        comment_results,
        base_domain,
        pagination_counts,
        js_render
    )

    summary = {
        "total": len(results),
        "valid": sum(1 for r in results if r["classification"] == "OK"),
        "broken": sum(1 for r in results if r["classification"] == "NOT_FOUND"),
        "errors": sum(1 for r in results if r["classification"] == "ERROR"),
    }

    return {
        "summary": summary,
        "results": results,
        "inline_results": inline_results,
        "comment_results": comment_results
    }