# state.py  — shared crawl state, imported by crawler.py and routes.py
import threading

STOP_EVENT = threading.Event()   # set() → abort crawl
CRAWL_LOCK = threading.Lock()    # prevents concurrent scans
IS_RUNNING  = threading.Event()  # set() while a crawl is active

# ---------------------------------------------------------------------------
# Progress tracking (thread-safe)
# ---------------------------------------------------------------------------
_progress_lock = threading.Lock()
_job_progress: dict = {}   # job_id → {"progress": 0, "pages_crawled": 0, "links_checked": 0}


def set_progress(job_id: str, progress: int, pages_crawled: int = 0, links_checked: int = 0):
    with _progress_lock:
        _job_progress[job_id] = {
            "progress":      min(max(progress, 0), 100),
            "pages_crawled": pages_crawled,
            "links_checked": links_checked,
        }


def get_progress(job_id: str) -> dict:
    with _progress_lock:
        return _job_progress.get(
            job_id,
            {"progress": 0, "pages_crawled": 0, "links_checked": 0}
        )


def clear_progress(job_id: str):
    with _progress_lock:
        _job_progress.pop(job_id, None)