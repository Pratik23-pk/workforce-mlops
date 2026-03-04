from __future__ import annotations

import pandas as pd

from workforce_mlops.models.promote_model import select_candidate


def test_select_candidate_prefers_top_ranked_threshold_pass() -> None:
    df = pd.DataFrame(
        [
            {
                "model": "m1",
                "val_composite": 1.0,
                "val_layoff_risk_auc": 0.70,
                "test_layoff_risk_auc": 0.68,
            },
            {
                "model": "m2",
                "val_composite": 1.2,
                "val_layoff_risk_auc": 0.72,
                "test_layoff_risk_auc": 0.71,
            },
        ]
    )
    policy = {
        "selection_metric": "val_composite",
        "lower_is_better": True,
        "fallback_model": "m2",
        "thresholds": {"val_layoff_risk_auc_min": 0.50, "test_layoff_risk_auc_min": 0.50},
    }

    selected, decision = select_candidate(df, policy)

    assert selected["model"] == "m1"
    assert decision["fallback_used"] is False


def test_select_candidate_skips_failed_threshold_and_takes_next() -> None:
    df = pd.DataFrame(
        [
            {
                "model": "m1",
                "val_composite": 0.9,
                "val_layoff_risk_auc": 0.40,
                "test_layoff_risk_auc": 0.39,
            },
            {
                "model": "m2",
                "val_composite": 1.1,
                "val_layoff_risk_auc": 0.70,
                "test_layoff_risk_auc": 0.72,
            },
        ]
    )
    policy = {
        "selection_metric": "val_composite",
        "lower_is_better": True,
        "fallback_model": "m1",
        "thresholds": {"val_layoff_risk_auc_min": 0.50, "test_layoff_risk_auc_min": 0.50},
    }

    selected, decision = select_candidate(df, policy)

    assert selected["model"] == "m2"
    assert decision["fallback_used"] is False
    assert decision["selected_rank"] == 2


def test_select_candidate_uses_fallback_when_all_fail() -> None:
    df = pd.DataFrame(
        [
            {
                "model": "baseline_mlp",
                "val_composite": 1.3,
                "val_layoff_risk_auc": 0.41,
                "test_layoff_risk_auc": 0.45,
            },
            {
                "model": "residual_mlp",
                "val_composite": 1.1,
                "val_layoff_risk_auc": 0.44,
                "test_layoff_risk_auc": 0.46,
            },
        ]
    )
    policy = {
        "selection_metric": "val_composite",
        "lower_is_better": True,
        "fallback_model": "baseline_mlp",
        "thresholds": {"val_layoff_risk_auc_min": 0.50, "test_layoff_risk_auc_min": 0.50},
    }

    selected, decision = select_candidate(df, policy)

    assert selected["model"] == "baseline_mlp"
    assert decision["fallback_used"] is True


def test_select_candidate_relaxes_auc_thresholds_when_all_auc_nan() -> None:
    df = pd.DataFrame(
        [
            {
                "model": "m1",
                "val_composite": 0.9,
                "val_layoff_risk_auc": float("nan"),
                "test_layoff_risk_auc": float("nan"),
            },
            {
                "model": "m2",
                "val_composite": 1.1,
                "val_layoff_risk_auc": float("nan"),
                "test_layoff_risk_auc": float("nan"),
            },
        ]
    )
    policy = {
        "selection_metric": "val_composite",
        "lower_is_better": True,
        "fallback_model": "m2",
        "thresholds": {"val_layoff_risk_auc_min": 0.50, "test_layoff_risk_auc_min": 0.50},
    }

    selected, decision = select_candidate(df, policy)

    assert selected["model"] == "m1"
    assert decision["fallback_used"] is False
    assert set(decision["auto_relaxed_thresholds"]) == {
        "val_layoff_risk_auc_min",
        "test_layoff_risk_auc_min",
    }
