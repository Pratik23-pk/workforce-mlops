from __future__ import annotations

from workforce_mlops.api.services.scenario import features_from_market_index, simulate_forecast


def test_features_from_market_index_stays_in_bounds() -> None:
    features = features_from_market_index(default_company="Acme", market_index=0, year=2027)

    assert features["company"] == "Acme"
    assert features["year"] == 2027
    assert 0 <= features["data_quality_score"] <= 100
    assert -40 <= features["stock_price_change_pct"] <= 40
    assert 0 <= features["unemployment_rate_us_pct"] <= 12


def test_simulate_forecast_returns_expected_horizon() -> None:
    forecast = simulate_forecast(
        year=2027,
        employees_start=10000,
        pred_hiring=1200,
        pred_layoffs=600,
        pred_risk=0.3,
        pred_volatility=0.2,
        market_index=70,
        horizon=6,
    )

    assert len(forecast) == 6
    assert forecast[0].year == 2027
    assert forecast[-1].year == 2032
    assert all(point.employees > 0 for point in forecast)
    assert all(0 <= point.layoff_risk_prob <= 1 for point in forecast)
