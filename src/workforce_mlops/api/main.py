from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from workforce_mlops.api.schemas import (
    CustomPredictionRequest,
    HealthResponse,
    PredictionResponse,
    PresetListResponse,
    PresetPredictionRequest,
    ScenarioPresetSummary,
    TimelineResponse,
)
from workforce_mlops.api.services.prediction import PredictionService
from workforce_mlops.api.services.timeline import TimelineService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = Path(__file__).resolve().parent / "web"
TEMPLATES = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


@lru_cache(maxsize=1)
def get_prediction_service() -> PredictionService:
    artifact_dir_env = os.getenv("MODEL_ARTIFACT_DIR")
    artifact_dir = (
        Path(artifact_dir_env)
        if artifact_dir_env
        else (PROJECT_ROOT / "artifacts" / "model")
    )
    return PredictionService(project_root=PROJECT_ROOT, artifact_dir=artifact_dir)


@lru_cache(maxsize=1)
def get_timeline_service() -> TimelineService:
    return TimelineService(project_root=PROJECT_ROOT)


@lru_cache(maxsize=1)
def get_cached_timeline() -> TimelineResponse:
    points = get_timeline_service().load_timeline()
    return TimelineResponse(points=points)


app = FastAPI(
    title="Workforce Forecast API",
    description="FastAPI backend for multi-task workforce forecasting",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")


@app.on_event("startup")
def warm_services() -> None:
    """Warm expensive services once to avoid first-request latency."""
    if os.getenv("WARM_MODEL_ON_STARTUP", "0") == "1":
        try:
            get_prediction_service()
        except (FileNotFoundError, ModuleNotFoundError, RuntimeError):
            # App can still serve UI and non-model endpoints while artifacts are unavailable.
            pass
    try:
        get_cached_timeline()
    except FileNotFoundError:
        pass


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/presets", response_model=PresetListResponse)
def list_presets() -> PresetListResponse:
    try:
        service = get_prediction_service()
        presets = [
            ScenarioPresetSummary(id=p.id, name=p.name, description=p.description)
            for p in service.list_presets()
        ]
        return PresetListResponse(presets=presets)
    except (FileNotFoundError, ModuleNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/timeline", response_model=TimelineResponse)
def timeline() -> TimelineResponse:
    try:
        return get_cached_timeline()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/predict/preset", response_model=PredictionResponse)
def predict_preset(payload: PresetPredictionRequest) -> PredictionResponse:
    try:
        service = get_prediction_service()
        return service.predict_from_preset(payload.preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ModuleNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/predict/custom", response_model=PredictionResponse)
def predict_custom(payload: CustomPredictionRequest) -> PredictionResponse:
    try:
        service = get_prediction_service()
        return service.predict_from_custom_market(payload.market_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ModuleNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
