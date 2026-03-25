from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.core.agent_core import FlowFixAgent
from app.models.schemas import AnalyzeRequest, AnalyzeResponse, BenchmarkResponse, HealthResponse


router = APIRouter()
agent = FlowFixAgent()


@router.get("/", response_class=HTMLResponse)
async def debug_ui() -> str:
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="flowfix-agent")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return await agent.analyze_issue(request.input)


@router.post("/benchmark", response_model=BenchmarkResponse)
async def benchmark() -> BenchmarkResponse:
    try:
        return await agent.run_benchmark()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
