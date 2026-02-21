from __future__ import annotations

REQUIRED_COLUMNS = [
    "company",
    "year",
    "employees_start",
    "employees_end",
    "new_hires",
    "layoffs",
    "net_change",
    "hiring_rate_pct",
    "attrition_rate_pct",
    "revenue_billions_usd",
    "stock_price_change_pct",
    "gdp_growth_us_pct",
    "unemployment_rate_us_pct",
    "is_estimated",
    "confidence_level",
    "data_quality_score",
]

TARGET_COLUMNS = [
    "target_hiring",
    "target_layoffs",
    "target_layoff_risk",
    "target_workforce_volatility",
]

DEFAULT_FEATURE_COLUMNS = [
    "company",
    "confidence_level",
    "year",
    "employees_start",
    "revenue_billions_usd",
    "stock_price_change_pct",
    "gdp_growth_us_pct",
    "unemployment_rate_us_pct",
    "is_estimated",
    "data_quality_score",
]
