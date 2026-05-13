import asyncio
import threading
import concurrent.futures
import requests

from config import (
    REQUEST_TIMEOUT,
    HEADERS,
    JS_RENDER_TIMEOUT,
    JS_SETTLE_MS,
    JS_RENDER_DEBUG,
)

# Thread-local storage for browser objects
_thread_local = threading.local()

# Small executor for Playwright tasks
_playwright_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="browser-worker"
)


class _BrowserGuard:
    """
    Simple cleanup helper for browser threads.
    """

    def __del__(self):
        close_thread_browser()


def _ensure_no_asyncio_loop():
    """
    Ensure Playwright is not started inside
    an already-running event loop.
    """

    try:
        loop = asyncio.get_event_loop()

        if loop.is_running():
            raise RuntimeError(
                "Cannot start Playwright inside active event loop"
            )

    except RuntimeError:
        pass

    try:
        asyncio.set_event_loop(None)
    except Exception:
        pass


def _close_playwright_objects():
    """
    Close browser-related objects safely.
    """

    browser = getattr(_thread_local, "browser", None)

    if browser:
        try:
            browser.close()
        except Exception:
            pass

        _thread_local.browser = None

    playwright = getattr(_thread_local, "playwright", None)

    if playwright:
        try:
            playwright.stop()
        except Exception:
            pass

        _thread_local.playwright = None


def close_thread_browser():
    """
    Cleanup browser resources for current thread.
    """

    if getattr(_thread_local, "browser", None):

        print(
            f"[PLAYWRIGHT] Closing browser on "
            f"{threading.current_thread().name}"
        )

        _close_playwright_objects()


def _get_browser():
    """
    Create browser instance lazily.
    """

    _ensure_no_asyncio_loop()

    browser = getattr(_thread_local, "browser", None)

    if browser is None:

        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()

        browser = playwright.chromium.launch(
            headless=True
        )

        _thread_local.playwright = playwright
        _thread_local.browser = browser
        _thread_local._guard = _BrowserGuard()

    return browser


def _fetch_with_playwright_sync(
    url: str,
    js_render_debug: bool = False
):
    """
    Fetch rendered HTML using Playwright.
    """

    context = None
    page = None

    try:
        browser = _get_browser()

        context = browser.new_context(
            user_agent=HEADERS.get(
                "User-Agent",
                "Mozilla/5.0"
            )
        )

        page = context.new_page()

        response = page.goto(
            url,
            timeout=JS_RENDER_TIMEOUT,
            wait_until="domcontentloaded"
        )

        # Wait additional time for dynamic content
        page.wait_for_timeout(JS_SETTLE_MS)

        html = page.content()

        status_code = None

        if response:
            status_code = response.status

        if js_render_debug:
            print(f"[DEBUG] HTML Preview for {url}")
            print(html[:1000])

        return html, status_code, ""

    except Exception as error:
        return None, None, f"Playwright error: {error}"

    finally:

        if page:
            try:
                page.close()
            except Exception:
                pass

        if context:
            try:
                context.close()
            except Exception:
                pass


def _fetch_with_playwright(
    url: str,
    js_render_debug: bool = False
):
    """
    Run Playwright fetch inside executor.
    """

    future = _playwright_executor.submit(
        _fetch_with_playwright_sync,
        url,
        js_render_debug
    )

    try:
        return future.result()

    except Exception as error:
        return None, None, f"Executor error: {error}"


def fetch_html(
    url: str,
    js_render: bool,
    session: requests.Session,
    js_render_debug: bool = JS_RENDER_DEBUG,
):
    """
    Fetch HTML content from a webpage.

    Supports:
    - normal requests
    - optional JS rendering
    """

    # Use Playwright when JS rendering is enabled
    if js_render:

        html, status_code, error = _fetch_with_playwright(
            url,
            js_render_debug
        )

        if html is not None:
            return html, status_code, error

        print(
            f"[HTML_FETCHER] Playwright failed for {url}"
        )

    # Fallback to requests
    try:

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )

        return response.text, response.status_code, ""

    except requests.exceptions.Timeout:
        return None, None, "Timeout"

    except requests.exceptions.ConnectionError:
        return None, None, "Connection failed"

    except requests.exceptions.TooManyRedirects:
        return None, None, "Too many redirects"

    except requests.exceptions.RequestException as error:
        return None, None, f"Request failed: {error}"