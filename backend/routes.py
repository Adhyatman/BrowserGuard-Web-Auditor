import threading
import uuid

jobs = {}
from fastapi import APIRouter, HTTPException
from schema import ScanRequest, ScanResponse
from crawler import run_checker_api
from crawler import state   # ← add this import
from ai_analyzer import analyze_with_ai

router = APIRouter()


def run_job(job_id: str, url: str, js_render: bool):

    state.STOP_EVENT.clear()
    try:
        jobs[job_id]["status"] = "running"

        result = run_checker_api(url, js_render=js_render, job_id=job_id)

        prev = state.get_progress(job_id)
        state.set_progress(
            job_id,
            progress=100,
            pages_crawled=prev["pages_crawled"],
            links_checked=prev["links_checked"],
        )

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

    finally:
        state.clear_progress(job_id)


def _run_scan(url_str: str, js_render: bool = False):
    try:
        data = run_checker_api(url_str, js_render=js_render)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {exc}")
    return data


@router.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Broken Link Checker API is running."}


@router.get("/status", tags=["Control"])
def crawl_status():
    return {
        "running": state.IS_RUNNING.is_set(),
        "stopped": state.STOP_EVENT.is_set(),
    }


@router.post("/stop", tags=["Control"])
def stop_crawl():
    state.STOP_EVENT.set()
    return {"status": "stop signal sent"}


@router.post("/scan", response_model=ScanResponse, tags=["Scan"])
def scan(request: ScanRequest):
    return _run_scan(str(request.url), js_render=request.js_render)


@router.post("/analyze")
def analyze(request: ScanRequest):
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status":    "queued",
        "result":    None,
        "error":     None,
        "ai_result": None,   # cache slot — None means not yet requested
    }

    thread = threading.Thread(
        target=run_job,
        args=(job_id, str(request.url), request.js_render),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "started"}


@router.get("/job/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    progress_data = state.get_progress(job_id)

    return {
        **job,
        "progress":      progress_data["progress"],
        "pages_crawled": progress_data["pages_crawled"],
        "links_checked": progress_data["links_checked"],
    }


@router.post("/job/{job_id}/ai", tags=["AI"])
def get_ai_insights(job_id: str):

    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed yet (status: {job['status']})"
        )

    if job["ai_result"] is not None:
        return job["ai_result"]

    ai_output = analyze_with_ai(job["result"])   
    jobs[job_id]["ai_result"] = ai_output      

    return ai_output