from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class ScenarioPresetSummary(BaseModel):
    id: str
    name: str
    description: str


class PresetListResponse(BaseModel):
    presets: list[ScenarioPresetSummary]


class PresetPredictionRequest(BaseModel):
    preset_id: str = Field(..., description="Scenario preset identifier")


class CustomPredictionRequest(BaseModel):
    market_index: float = Field(
        ...,
        ge=0,
        le=100,
        description="0=extreme recession, 100=extreme expansion",
    )


class PredictionValues(BaseModel):
    hiring: float
    layoffs: float
    layoff_risk_prob: float
    workforce_volatility: float


class ForecastPoint(BaseModel):
    year: int
    employees: float
    hiring: float
    layoffs: float
    layoff_risk_prob: float
    workforce_volatility: float


class PredictionResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    scenario_description: str
    features: dict[str, Any]
    predictions: PredictionValues
    forecast: list[ForecastPoint]


class TimelinePoint(BaseModel):
    year: int
    hiring: float
    layoffs: float
    net_change: float


class TimelineResponse(BaseModel):
    points: list[TimelinePoint]
