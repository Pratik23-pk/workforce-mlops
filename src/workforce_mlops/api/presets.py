from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioPreset:
    id: str
    name: str
    description: str
    features: dict[str, float | int | str]


def build_presets(default_company: str, base_year: int) -> dict[str, ScenarioPreset]:
    presets = [
        ScenarioPreset(
            id="aggressive_expansion",
            name="Aggressive Expansion",
            description="Strong economic growth, high hiring appetite, low unemployment.",
            features={
                "company": default_company,
                "confidence_level": "High",
                "year": base_year,
                "employees_start": 18000,
                "revenue_billions_usd": 45.0,
                "stock_price_change_pct": 28.0,
                "gdp_growth_us_pct": 3.6,
                "unemployment_rate_us_pct": 3.4,
                "is_estimated": 0,
                "data_quality_score": 92,
            },
        ),
        ScenarioPreset(
            id="cost_cut_recession",
            name="Cost-Cut Recession",
            description=(
                "Macroeconomic downturn with strong cost controls and elevated "
                "unemployment."
            ),
            features={
                "company": default_company,
                "confidence_level": "Medium",
                "year": base_year,
                "employees_start": 22000,
                "revenue_billions_usd": 12.0,
                "stock_price_change_pct": -24.0,
                "gdp_growth_us_pct": -1.8,
                "unemployment_rate_us_pct": 8.7,
                "is_estimated": 1,
                "data_quality_score": 78,
            },
        ),
        ScenarioPreset(
            id="automation_transition",
            name="Automation Transition",
            description=(
                "Stable market but workforce reshaping due to automation and skills shifts."
            ),
            features={
                "company": default_company,
                "confidence_level": "High",
                "year": base_year,
                "employees_start": 15000,
                "revenue_billions_usd": 25.0,
                "stock_price_change_pct": 8.0,
                "gdp_growth_us_pct": 2.0,
                "unemployment_rate_us_pct": 5.2,
                "is_estimated": 1,
                "data_quality_score": 86,
            },
        ),
    ]
    return {preset.id: preset for preset in presets}
