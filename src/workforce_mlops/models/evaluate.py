from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_absolute_error, mean_squared_error, roc_auc_score

from workforce_mlops.mlflow_utils import get_configured_mlflow, log_repro_context
from workforce_mlops.models.predict import predict_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate trained model on test set")
    parser.add_argument("--test-path", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--report-path", required=True)
    return parser.parse_args()


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def main() -> None:
    args = parse_args()
    mlflow = get_configured_mlflow(default_experiment_name="workforce-evaluation")

    df = pd.read_csv(args.test_path)
    pred = predict_df(df, args.artifact_dir)

    risk_true = df["target_layoff_risk"].to_numpy(dtype=int)
    risk_prob = pred["pred_layoff_risk_prob"].to_numpy()
    risk_label = (risk_prob >= 0.5).astype(int)

    try:
        auc = float(roc_auc_score(risk_true, risk_prob))
    except ValueError:
        auc = float("nan")

    metrics = {
        "hiring_rmse": rmse(df["target_hiring"].to_numpy(), pred["pred_hiring"].to_numpy()),
        "hiring_mae": float(
            mean_absolute_error(df["target_hiring"].to_numpy(), pred["pred_hiring"].to_numpy())
        ),
        "layoffs_rmse": rmse(df["target_layoffs"].to_numpy(), pred["pred_layoffs"].to_numpy()),
        "layoffs_mae": float(
            mean_absolute_error(df["target_layoffs"].to_numpy(), pred["pred_layoffs"].to_numpy())
        ),
        "volatility_rmse": rmse(
            df["target_workforce_volatility"].to_numpy(),
            pred["pred_workforce_volatility"].to_numpy(),
        ),
        "volatility_mae": float(
            mean_absolute_error(
                df["target_workforce_volatility"].to_numpy(),
                pred["pred_workforce_volatility"].to_numpy(),
            )
        ),
        "layoff_risk_auc": auc,
        "layoff_risk_f1": float(f1_score(risk_true, risk_label, zero_division=0)),
    }

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    with mlflow.start_run(run_name="evaluate-production-model"):
        mlflow.set_tags({"project": "workforce-mlops", "stage": "evaluate"})
        log_repro_context(mlflow)
        mlflow.log_params(
            {
                "test_path": args.test_path,
                "artifact_dir": args.artifact_dir,
                "rows": int(len(df)),
            }
        )
        for key, value in metrics.items():
            if np.isfinite(value):
                mlflow.log_metric(key, float(value))
        mlflow.log_artifact(str(report_path))

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
