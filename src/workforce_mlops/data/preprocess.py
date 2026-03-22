from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml
from sklearn.model_selection import train_test_split

from workforce_mlops.config import DEFAULT_FEATURE_COLUMNS
from workforce_mlops.mlflow_utils import get_configured_mlflow, log_repro_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Feature engineering + train/val/test split")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--train-output", required=True, help="Train CSV output path")
    parser.add_argument("--val-output", required=True, help="Validation CSV output path")
    parser.add_argument("--test-output", required=True, help="Test CSV output path")
    parser.add_argument("--params", required=True, help="Params YAML path")
    return parser.parse_args()


def add_targets(df: pd.DataFrame, layoff_risk_threshold: float) -> pd.DataFrame:
    df = df.copy()
    denom = df["employees_start"].clip(lower=1)

    df["target_hiring"] = df["new_hires"].astype(float)
    df["target_layoffs"] = df["layoffs"].astype(float)
    df["target_layoff_risk"] = ((df["layoffs"] / denom) >= layoff_risk_threshold).astype(int)
    df["target_workforce_volatility"] = (
        (df["new_hires"] + df["layoffs"]) / denom
    ).astype(float)

    df["is_estimated"] = df["is_estimated"].astype(int)
    return df


def split_by_time(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    years = sorted(df["year"].unique().tolist())

    if len(years) >= 3:
        test_year = years[-1]
        val_year = years[-2]

        train_df = df[df["year"] < val_year].copy()
        val_df = df[df["year"] == val_year].copy()
        test_df = df[df["year"] == test_year].copy()

        if len(train_df) > 0 and len(val_df) > 0 and len(test_df) > 0:
            return train_df, val_df, test_df

    train_df, temp_df = train_test_split(df, test_size=0.30, random_state=42)
    val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42)
    return train_df, val_df, test_df


def main() -> None:
    args = parse_args()

    params = yaml.safe_load(Path(args.params).read_text(encoding="utf-8"))
    layoff_risk_threshold = float(params["targets"]["layoff_risk_threshold"])

    df = pd.read_csv(args.input)
    df = add_targets(df, layoff_risk_threshold)

    selected_cols = DEFAULT_FEATURE_COLUMNS + [
        "target_hiring",
        "target_layoffs",
        "target_layoff_risk",
        "target_workforce_volatility",
    ]
    model_df = df[selected_cols].copy()

    train_df, val_df, test_df = split_by_time(model_df)

    Path(args.train_output).parent.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(args.train_output, index=False)
    val_df.to_csv(args.val_output, index=False)
    test_df.to_csv(args.test_output, index=False)

    mlflow = get_configured_mlflow(default_experiment_name="workforce-preprocess")
    with mlflow.start_run(run_name="preprocess-split"):
        mlflow.set_tags({"project": "workforce-mlops", "stage": "preprocess"})
        log_repro_context(mlflow)
        mlflow.log_params(
            {
                "input_path": str(args.input),
                "train_output": str(args.train_output),
                "val_output": str(args.val_output),
                "test_output": str(args.test_output),
                "layoff_risk_threshold": float(layoff_risk_threshold),
            }
        )
        mlflow.log_metrics(
            {
                "train_rows": float(len(train_df)),
                "val_rows": float(len(val_df)),
                "test_rows": float(len(test_df)),
            }
        )

    print(
        "Saved splits | "
        f"train={len(train_df)}, val={len(val_df)}, test={len(test_df)}"
    )


if __name__ == "__main__":
    main()
