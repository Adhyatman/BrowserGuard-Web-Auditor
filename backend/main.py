"""
Entry point.
Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import urllib3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router
from dotenv import load_dotenv
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(
    title="Broken Link Checker API",
    description="REST API wrapper for the broken-link crawler.",
    version="1.0.0",
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

app.add_middleware(
    CORSMiddleware,
    # allow_origins=[
    #     "http://localhost:5173",
    #     "http://localhost:3000",
    #     "http://127.0.0.1:5173",
    # ],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
