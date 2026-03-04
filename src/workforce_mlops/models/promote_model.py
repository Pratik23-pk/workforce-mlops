from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from workforce_mlops.config import TARGET_COLUMNS
from workforce_mlops.mlflow_utils import get_configured_mlflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote best comparison model for inference")
    parser.add_argument(
        "--comparison-report",
        default="reports/model_comparison.csv",
        help="Path to model comparison CSV report",
    )
    parser.add_argument(
        "--summary-path",
        default="reports/model_comparison_summary.json",
        help="Path to model comparison summary JSON",
    )
    parser.add_argument(
        "--experiments-dir",
        default="artifacts/experiments",
        help="Directory containing per-model experiment artifacts",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/model",
        help="Promoted production model artifact directory",
    )
    parser.add_argument(
        "--params",
        default="params.yaml",
        help="Params YAML path (used for feature metadata and policy)",
    )
    parser.add_argument(
        "--promotion-report",
        default="reports/model_promotion.json",
        help="Output JSON report for promotion decision",
    )
    return parser.parse_args()


def load_policy(params: dict[str, Any]) -> dict[str, Any]:
    cfg = params.get("model_selection", {})
    return {
        "selection_metric": cfg.get("selection_metric", "val_composite"),
        "lower_is_better": bool(cfg.get("lower_is_better", True)),
        "fallback_model": cfg.get("fallback_model", "baseline_mlp"),
        "thresholds": {
            "val_layoff_risk_auc_min": cfg.get("val_layoff_risk_auc_min", 0.50),
            "test_layoff_risk_auc_min": cfg.get("test_layoff_risk_auc_min", 0.50),
            "val_hiring_rmse_max": cfg.get("val_hiring_rmse_max"),
            "val_layoffs_rmse_max": cfg.get("val_layoffs_rmse_max"),
            "val_volatility_rmse_max": cfg.get("val_volatility_rmse_max"),
        },
    }


def _is_finite_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def row_passes_thresholds(row: pd.Series, thresholds: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    def require_min(metric: str, threshold_key: str) -> None:
        threshold = thresholds.get(threshold_key)
        if threshold is None:
            return
        value = row.get(metric)
        if not _is_finite_number(value):
            reasons.append(f"{metric} is not finite")
            return
        if float(value) < float(threshold):
            reasons.append(f"{metric}={float(value):.4f} < {float(threshold):.4f}")

    def require_max(metric: str, threshold_key: str) -> None:
        threshold = thresholds.get(threshold_key)
        if threshold is None:
            return
        value = row.get(metric)
        if not _is_finite_number(value):
            reasons.append(f"{metric} is not finite")
            return
        if float(value) > float(threshold):
            reasons.append(f"{metric}={float(value):.4f} > {float(threshold):.4f}")

    require_min("val_layoff_risk_auc", "val_layoff_risk_auc_min")
    require_min("test_layoff_risk_auc", "test_layoff_risk_auc_min")
    require_max("val_hiring_rmse", "val_hiring_rmse_max")
    require_max("val_layoffs_rmse", "val_layoffs_rmse_max")
    require_max("val_volatility_rmse", "val_volatility_rmse_max")

    return len(reasons) == 0, reasons


def select_candidate(
    results: pd.DataFrame,
    policy: dict[str, Any],
) -> tuple[pd.Series, dict[str, Any]]:
    metric = str(policy["selection_metric"])
    lower_is_better = bool(policy["lower_is_better"])
    fallback_model = str(policy["fallback_model"])
    thresholds = dict(policy["thresholds"])
    auto_relaxed_thresholds: list[str] = []

    if metric not in results.columns:
        raise ValueError(f"Selection metric '{metric}' not found in comparison report columns.")

    sorted_df = results.sort_values(metric, ascending=lower_is_better).reset_index(drop=True)

    # When the split has a single class for layoff risk, AUC is undefined (NaN) for all models.
    # In that case we relax only the corresponding AUC thresholds and keep other checks enforced.
    auc_threshold_map = {
        "val_layoff_risk_auc_min": "val_layoff_risk_auc",
        "test_layoff_risk_auc_min": "test_layoff_risk_auc",
    }
    for threshold_key, metric_name in auc_threshold_map.items():
        threshold_value = thresholds.get(threshold_key)
        if threshold_value is None or metric_name not in sorted_df.columns:
            continue
        if not any(_is_finite_number(v) for v in sorted_df[metric_name].tolist()):
            thresholds[threshold_key] = None
            auto_relaxed_thresholds.append(threshold_key)

    audit: list[dict[str, Any]] = []

    for rank, (_, row) in enumerate(sorted_df.iterrows(), start=1):
        passed, failures = row_passes_thresholds(row, thresholds)
        audit.append(
            {
                "rank": rank,
                "model": row["model"],
                "metric": metric,
                "metric_value": float(row[metric]),
                "passed_thresholds": passed,
                "failures": failures,
            }
        )
        if passed:
            return row, {
                "audit": audit,
                "selected_rank": rank,
                "selection_reason": "top_ranked_threshold_pass",
                "fallback_used": False,
                "auto_relaxed_thresholds": auto_relaxed_thresholds,
            }

    if fallback_model in set(sorted_df["model"].tolist()):
        chosen = sorted_df.loc[sorted_df["model"] == fallback_model].iloc[0]
        rank = int(sorted_df.index[sorted_df["model"] == fallback_model][0]) + 1
        return chosen, {
                "audit": audit,
                "selected_rank": rank,
                "selection_reason": "fallback_model_used_after_threshold_failures",
                "fallback_used": True,
                "auto_relaxed_thresholds": auto_relaxed_thresholds,
            }

    chosen = sorted_df.iloc[0]
    return chosen, {
        "audit": audit,
        "selected_rank": 1,
        "selection_reason": "no_candidate_passed_thresholds_or_fallback_missing",
        "fallback_used": False,
        "auto_relaxed_thresholds": auto_relaxed_thresholds,
    }


def promote_best_model(
    comparison_report: str,
    summary_path: str,
    experiments_dir: str,
    output_dir: str,
    params_path: str,
    promotion_report: str,
) -> dict[str, Any]:
    mlflow = get_configured_mlflow(default_experiment_name="workforce-model-promotion")
    report_df = pd.read_csv(comparison_report)
    if report_df.empty:
        raise ValueError("Comparison report is empty; cannot promote a model.")
    if "model" not in report_df.columns:
        raise ValueError("Comparison report missing required 'model' column.")

    params = yaml.safe_load(Path(params_path).read_text(encoding="utf-8"))
    policy = load_policy(params)
    selected_row, decision = select_candidate(report_df, policy)

    selected_model = str(selected_row["model"])
    experiments_root = Path(experiments_dir)
    selected_model_dir = experiments_root / selected_model
    selected_model_path = selected_model_dir / "model.pt"
    selected_metadata_path = selected_model_dir / "metadata.json"
    shared_preprocessor_path = experiments_root / "shared_preprocessor.joblib"

    if not selected_model_path.exists():
        raise FileNotFoundError(f"Missing selected model weights: {selected_model_path}")
    if not selected_metadata_path.exists():
        raise FileNotFoundError(f"Missing selected model metadata: {selected_metadata_path}")
    if not shared_preprocessor_path.exists():
        raise FileNotFoundError(f"Missing shared preprocessor: {shared_preprocessor_path}")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    promoted_model_path = output_root / "model.pt"
    promoted_preprocessor_path = output_root / "preprocessor.joblib"
    promoted_metadata_path = output_root / "metadata.json"

    shutil.copy2(selected_model_path, promoted_model_path)
    shutil.copy2(shared_preprocessor_path, promoted_preprocessor_path)

    selected_metadata = json.loads(selected_metadata_path.read_text(encoding="utf-8"))
    categorical_cols = list(params["features"]["categorical"])
    numeric_cols = list(params["features"]["numerical"])
    feature_cols = categorical_cols + numeric_cols

    selected_metadata["feature_columns"] = selected_metadata.get("feature_columns", feature_cols)
    selected_metadata["categorical_columns"] = selected_metadata.get(
        "categorical_columns",
        categorical_cols,
    )
    selected_metadata["numerical_columns"] = selected_metadata.get(
        "numerical_columns",
        numeric_cols,
    )
    selected_metadata["target_columns"] = selected_metadata.get("target_columns", TARGET_COLUMNS)
    selected_metadata["promoted_at_utc"] = datetime.now(timezone.utc).isoformat()
    selected_metadata["promotion_source_model"] = selected_model
    selected_metadata["promotion_selection_metric"] = policy["selection_metric"]

    promoted_metadata_path.write_text(json.dumps(selected_metadata, indent=2), encoding="utf-8")

    # IMPORTANT: keep compare_models outputs immutable in later stages.
    # We only read the summary for context and write promotion details to
    # reports/model_promotion.json to avoid DVC stage dependency churn.
    summary_file = Path(summary_path)
    summary_loaded = summary_file.exists()

    promo_report = {
        "promoted_model": selected_model,
        "comparison_summary_path": str(summary_file),
        "comparison_summary_loaded": summary_loaded,
        "selection_metric": policy["selection_metric"],
        "selected_metric_value": float(selected_row[policy["selection_metric"]]),
        "selection_reason": decision["selection_reason"],
        "selected_rank": int(decision["selected_rank"]),
        "fallback_used": bool(decision["fallback_used"]),
        "auto_relaxed_thresholds": decision.get("auto_relaxed_thresholds", []),
        "threshold_policy": policy["thresholds"],
        "audit": decision["audit"],
        "output_model_path": str(promoted_model_path),
        "output_preprocessor_path": str(promoted_preprocessor_path),
        "output_metadata_path": str(promoted_metadata_path),
    }

    promotion_path = Path(promotion_report)
    promotion_path.parent.mkdir(parents=True, exist_ok=True)
    promotion_path.write_text(json.dumps(promo_report, indent=2), encoding="utf-8")

    with mlflow.start_run(run_name="promote-best-model"):
        mlflow.set_tags({"project": "workforce-mlops", "stage": "promote_model"})
        mlflow.log_params(
            {
                "selection_metric": policy["selection_metric"],
                "promoted_model": selected_model,
                "selection_reason": decision["selection_reason"],
                "selected_rank": int(decision["selected_rank"]),
                "fallback_used": bool(decision["fallback_used"]),
                "auto_relaxed_thresholds": ",".join(decision.get("auto_relaxed_thresholds", [])),
            }
        )
        for column in report_df.columns:
            if column in {"model"}:
                continue
            value = selected_row.get(column)
            if _is_finite_number(value):
                mlflow.log_metric(f"selected_{column}", float(value))
        mlflow.log_artifact(str(promotion_path))
        mlflow.log_artifact(str(promoted_metadata_path))

    return promo_report


def main() -> None:
    args = parse_args()
    promo_report = promote_best_model(
        comparison_report=args.comparison_report,
        summary_path=args.summary_path,
        experiments_dir=args.experiments_dir,
        output_dir=args.output_dir,
        params_path=args.params,
        promotion_report=args.promotion_report,
    )
    print(json.dumps(promo_report, indent=2))


if __name__ == "__main__":
    main()
