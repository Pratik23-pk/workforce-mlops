from __future__ import annotations

import numpy as np

from workforce_mlops.api.schemas import ForecastPoint


def features_from_market_index(
    default_company: str,
    market_index: float,
    year: int,
) -> dict[str, float | int | str]:
    idx = float(np.clip(market_index, 0.0, 100.0))
    stress = (50.0 - idx) / 50.0

    revenue = float(np.clip(20.0 + (idx - 50.0) * 0.35, 5.0, 60.0))
    stock_change = float(np.clip((idx - 50.0) * 0.9, -35.0, 35.0))
    gdp_growth = float(np.clip(1.8 + (idx - 50.0) * 0.06, -3.5, 5.5))
    unemployment = float(np.clip(5.0 + stress * 3.0, 2.5, 9.5))
    quality = int(np.clip(84 - abs(idx - 50.0) * 0.2, 60.0, 95.0))

    return {
        "company": default_company,
        "confidence_level": "High" if idx >= 60 else "Medium",
        "year": int(year),
        "employees_start": 16000,
        "revenue_billions_usd": revenue,
        "stock_price_change_pct": stock_change,
        "gdp_growth_us_pct": gdp_growth,
        "unemployment_rate_us_pct": unemployment,
        "is_estimated": 1,
        "data_quality_score": quality,
    }


def simulate_forecast(
    year: int,
    employees_start: float,
    pred_hiring: float,
    pred_layoffs: float,
    pred_risk: float,
    pred_volatility: float,
    market_index: float,
    horizon: int = 6,
) -> list[ForecastPoint]:
    idx = float(np.clip(market_index, 0.0, 100.0))
    sentiment = (idx - 50.0) / 50.0

    employees = float(max(employees_start, 1.0))
    points: list[ForecastPoint] = []

    for step in range(horizon):
        trend = 1.0 + sentiment * 0.05 * step

        hiring = max(pred_hiring * trend, 0.0)
        layoffs = max(pred_layoffs * (1.0 - sentiment * 0.04 * step), 0.0)

        risk_raw = pred_risk + (0.45 - pred_risk) * (step / max(horizon - 1, 1)) * -sentiment
        risk = float(np.clip(risk_raw, 0.0, 1.0))

        volatility = max(pred_volatility * (1.0 + abs(sentiment) * 0.08 * step), 0.0)

        employees = max(employees + hiring - layoffs, 1.0)

        points.append(
            ForecastPoint(
                year=year + step,
                employees=float(employees),
                hiring=float(hiring),
                layoffs=float(layoffs),
                layoff_risk_prob=risk,
                workforce_volatility=float(volatility),
            )
        )

    return points
