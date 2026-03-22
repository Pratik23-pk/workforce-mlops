from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from workforce_mlops.config import REQUIRED_COLUMNS
from workforce_mlops.mlflow_utils import get_configured_mlflow, log_repro_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dataset schema")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--report", required=True, help="Validation report JSON path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    report_path = Path(args.report)

    df = pd.read_csv(in_path)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    report = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_columns": missing_cols,
        "null_counts": {k: int(v) for k, v in df.isnull().sum().to_dict().items()},
        "valid": len(missing_cols) == 0,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    mlflow = get_configured_mlflow(default_experiment_name="workforce-data-validation")
    with mlflow.start_run(run_name="data-validation"):
        mlflow.set_tags({"project": "workforce-mlops", "stage": "validate"})
        log_repro_context(mlflow)
        mlflow.log_params({"input_path": str(in_path)})
        mlflow.log_metrics(
            {
                "rows": float(report["rows"]),
                "columns": float(report["columns"]),
                "missing_columns": float(len(missing_cols)),
                "null_total": float(sum(report["null_counts"].values())),
                "valid": 1.0 if report["valid"] else 0.0,
            }
        )
        mlflow.log_artifact(str(report_path))

    if missing_cols:
        raise ValueError(f"Validation failed. Missing columns: {missing_cols}")

    print(f"Validation passed. Report saved to {report_path}")


if __name__ == "__main__":
    main()
