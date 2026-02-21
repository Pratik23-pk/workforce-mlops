from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from workforce_mlops.models.predict import predict_df

st.set_page_config(page_title="Workforce MLOps", page_icon="📊", layout="wide")

st.title("Workforce Forecasting (Multi-Task DNN)")
st.caption(
    "Predict hiring, layoffs, layoff risk probability, and workforce volatility "
    "from company/year inputs."
)

artifact_dir = Path("artifacts/model")

with st.form("predict_form"):
    col1, col2 = st.columns(2)

    with col1:
        company = st.text_input("Company", value="ExampleCorp")
        confidence_level = st.selectbox("Confidence level", options=["low", "medium", "high"])
        year = st.number_input("Year", min_value=1990, max_value=2100, value=2025, step=1)
        employees_start = st.number_input(
            "Employees at start", min_value=1, max_value=2_000_000, value=10000, step=100
        )
        revenue_billions_usd = st.number_input(
            "Revenue (billions USD)", min_value=0.0, max_value=10_000.0, value=10.0, step=0.1
        )

    with col2:
        stock_price_change_pct = st.number_input(
            "Stock price change %", min_value=-100.0, max_value=500.0, value=0.0, step=0.5
        )
        gdp_growth_us_pct = st.number_input(
            "US GDP growth %", min_value=-20.0, max_value=20.0, value=2.0, step=0.1
        )
        unemployment_rate_us_pct = st.number_input(
            "US unemployment rate %", min_value=0.0, max_value=50.0, value=4.0, step=0.1
        )
        is_estimated = st.checkbox("Estimated data", value=False)
        data_quality_score = st.slider("Data quality score", min_value=0, max_value=100, value=80)

    submitted = st.form_submit_button("Predict")

if submitted:
    if not artifact_dir.exists():
        st.error("Model artifacts not found at artifacts/model. Train the model first.")
    else:
        payload = pd.DataFrame(
            [
                {
                    "company": company,
                    "confidence_level": confidence_level,
                    "year": int(year),
                    "employees_start": int(employees_start),
                    "revenue_billions_usd": float(revenue_billions_usd),
                    "stock_price_change_pct": float(stock_price_change_pct),
                    "gdp_growth_us_pct": float(gdp_growth_us_pct),
                    "unemployment_rate_us_pct": float(unemployment_rate_us_pct),
                    "is_estimated": int(is_estimated),
                    "data_quality_score": int(data_quality_score),
                }
            ]
        )

        pred = predict_df(payload, artifact_dir).iloc[0]

        a, b, c, d = st.columns(4)
        a.metric("Pred Hiring", f"{pred['pred_hiring']:.2f}")
        b.metric("Pred Layoffs", f"{pred['pred_layoffs']:.2f}")
        c.metric("Layoff Risk Prob", f"{pred['pred_layoff_risk_prob']:.2%}")
        d.metric("Workforce Volatility", f"{pred['pred_workforce_volatility']:.4f}")

        st.write("Model bundle:", str(artifact_dir.resolve()))
