from pydantic import BaseModel, HttpUrl


class ScanRequest(BaseModel):
    url: HttpUrl
    js_render: bool = False


class ScanSummary(BaseModel):
    total: int
    valid: int
    broken: int
    redirects: int
    forbidden: int
    blocked: int
    rate_limited: int
    server_errors: int
    errors: int
    unique: int


class LinkResult(BaseModel):
    url: str
    status_code: int | None
    classification: str
    error: str
    source: str
    link_type: str


class InlineResult(BaseModel):
    page_url: str
    type: str
    # element: str
    # attribute: str
    # code_snippet: str
    dom_snippet: str
    resource_url: str | None = None  # populated for "External CSS" only


class ScanResponse(BaseModel):
    summary: ScanSummary
    results: list[LinkResult]
    inline_results: list[InlineResult] = []
    comment_results: list[InlineResult] = []