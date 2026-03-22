from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.metrics import f1_score, mean_absolute_error, mean_squared_error, roc_auc_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from workforce_mlops.config import DEFAULT_FEATURE_COLUMNS, TARGET_COLUMNS
from workforce_mlops.data.preprocess import add_targets, split_by_time
from workforce_mlops.mlflow_utils import get_configured_mlflow, log_repro_context

TORCH_MODULE = None
NN_MODULE = None
DATALOADER_MODULE = None
TENSORDATASET_MODULE = None


def require_torch():
    global TORCH_MODULE, NN_MODULE, DATALOADER_MODULE, TENSORDATASET_MODULE

    if TORCH_MODULE is not None:
        return TORCH_MODULE, NN_MODULE, DATALOADER_MODULE, TENSORDATASET_MODULE

    try:
        from torch import nn as nn_mod  # noqa: I001
        from torch.utils.data import (
            DataLoader as dataloader_mod,
            TensorDataset as tensor_dataset_mod,
        )
        import torch as torch_mod
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyTorch is required for model comparison. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    TORCH_MODULE = torch_mod
    NN_MODULE = nn_mod
    DATALOADER_MODULE = dataloader_mod
    TENSORDATASET_MODULE = tensor_dataset_mod
    return TORCH_MODULE, NN_MODULE, DATALOADER_MODULE, TENSORDATASET_MODULE


@dataclass
class ModelSpec:
    name: str
    kind: str
    hidden_dims: list[int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and compare 3 neural models")
    parser.add_argument(
        "--input-path",
        default="data/interim/workforce_clean.csv",
        help="Input dataset path (raw/interim)",
    )
    parser.add_argument("--params", default="params.yaml", help="Params YAML path")
    parser.add_argument(
        "--output-report",
        default="reports/model_comparison.csv",
        help="CSV report path",
    )
    parser.add_argument(
        "--output-summary",
        default="reports/model_comparison_summary.json",
        help="JSON summary path",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/experiments",
        help="Directory to save experiment artifacts",
    )
    return parser.parse_args()


def set_seed(seed: int) -> None:
    torch_mod, _, _, _ = require_torch()
    np.random.seed(seed)
    torch_mod.manual_seed(seed)
    torch_mod.cuda.manual_seed_all(seed)


def resolve_input_path(input_path: str) -> Path:
    primary = Path(input_path)
    if primary.exists():
        return primary

    fallback = Path("data/raw/workforce.csv")
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        f"Could not find input data at '{primary}' or fallback '{fallback}'."
    )


def build_preprocessor(numeric_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
        ],
        remainder="drop",
    )


def to_dense(matrix) -> np.ndarray:
    if hasattr(matrix, "toarray"):
        return matrix.toarray()
    return np.asarray(matrix)


def prepare_targets(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "hiring": df["target_hiring"].to_numpy(dtype=np.float32),
        "layoffs": df["target_layoffs"].to_numpy(dtype=np.float32),
        "layoff_risk": df["target_layoff_risk"].to_numpy(dtype=np.float32),
        "workforce_volatility": df["target_workforce_volatility"].to_numpy(dtype=np.float32),
    }


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def evaluate(model, x, y) -> dict[str, float]:
    torch_mod, _, _, _ = require_torch()
    model.eval()
    with torch_mod.no_grad():
        out = model(x)

    pred_hiring = out["hiring"].cpu().numpy()
    pred_layoffs = out["layoffs"].cpu().numpy()
    logits = out["layoff_risk_logits"].cpu().numpy()
    pred_vol = out["workforce_volatility"].cpu().numpy()

    risk_prob = 1.0 / (1.0 + np.exp(-np.clip(logits, -60.0, 60.0)))
    risk_label = (risk_prob >= 0.5).astype(int)

    risk_true = y["layoff_risk"].cpu().numpy().astype(int)
    try:
        risk_auc = float(roc_auc_score(risk_true, risk_prob))
    except ValueError:
        risk_auc = float("nan")

    return {
        "hiring_rmse": rmse(y["hiring"].cpu().numpy(), pred_hiring),
        "hiring_mae": float(mean_absolute_error(y["hiring"].cpu().numpy(), pred_hiring)),
        "layoffs_rmse": rmse(y["layoffs"].cpu().numpy(), pred_layoffs),
        "layoffs_mae": float(mean_absolute_error(y["layoffs"].cpu().numpy(), pred_layoffs)),
        "volatility_rmse": rmse(y["workforce_volatility"].cpu().numpy(), pred_vol),
        "volatility_mae": float(
            mean_absolute_error(y["workforce_volatility"].cpu().numpy(), pred_vol)
        ),
        "layoff_risk_auc": risk_auc,
        "layoff_risk_f1": float(f1_score(risk_true, risk_label, zero_division=0)),
    }


def build_model(spec: ModelSpec, input_dim: int, dropout: float):
    from workforce_mlops.models.model_factory import build_model as build_model_by_kind

    return build_model_by_kind(
        model_kind=spec.kind,
        input_dim=input_dim,
        hidden_dims=spec.hidden_dims,
        dropout=dropout,
    )


def train_single_model(
    spec: ModelSpec,
    train_cfg: dict,
    x_train_t,
    y_train_t: dict[str, Any],
    x_val_t,
    y_val_t: dict[str, Any],
    x_test_t,
    y_test_t: dict[str, Any],
    feature_columns: list[str],
    categorical_cols: list[str],
    numeric_cols: list[str],
    artifact_root: Path,
    mlflow_client: Any,
) -> dict[str, float]:
    torch_mod, nn, DataLoader, TensorDataset = require_torch()
    model = build_model(spec, input_dim=x_train_t.shape[1], dropout=float(train_cfg["dropout"]))

    loader = DataLoader(
        TensorDataset(
            x_train_t,
            y_train_t["hiring"],
            y_train_t["layoffs"],
            y_train_t["layoff_risk"],
            y_train_t["workforce_volatility"],
        ),
        batch_size=int(train_cfg["batch_size"]),
        shuffle=True,
    )

    mse = nn.MSELoss()
    bce = nn.BCEWithLogitsLoss()
    optimizer = torch_mod.optim.Adam(
        model.parameters(),
        lr=float(train_cfg["lr"]),
        weight_decay=float(train_cfg["weight_decay"]),
    )

    best_score = float("inf")
    best_state = None
    patience = int(train_cfg["early_stopping_patience"])
    patience_counter = 0

    weights = train_cfg["loss_weights"]
    epochs = int(train_cfg["epochs"])

    for _epoch in range(epochs):
        model.train()

        for batch in loader:
            x_b, y_h, y_l, y_r, y_v = batch
            out = model(x_b)

            loss = (
                float(weights["hiring"]) * mse(out["hiring"], y_h)
                + float(weights["layoffs"]) * mse(out["layoffs"], y_l)
                + float(weights["layoff_risk"]) * bce(out["layoff_risk_logits"], y_r)
                + float(weights["workforce_volatility"])
                * mse(out["workforce_volatility"], y_v)
            )

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        val_metrics = evaluate(model, x_val_t, y_val_t)
        val_score = (
            val_metrics["hiring_rmse"]
            + val_metrics["layoffs_rmse"]
            + val_metrics["volatility_rmse"]
        )

        if val_score < best_score:
            best_score = val_score
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= patience:
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    val_metrics = evaluate(model, x_val_t, y_val_t)
    test_metrics = evaluate(model, x_test_t, y_test_t)

    model_dir = artifact_root / spec.name
    model_dir.mkdir(parents=True, exist_ok=True)
    torch_mod.save(model.state_dict(), model_dir / "model.pt")

    meta = {
        "model_name": spec.name,
        "model_kind": spec.kind,
        "hidden_dims": spec.hidden_dims,
        "dropout": float(train_cfg["dropout"]),
        "input_dim": int(x_train_t.shape[1]),
        "feature_columns": feature_columns,
        "categorical_columns": categorical_cols,
        "numerical_columns": numeric_cols,
        "target_columns": TARGET_COLUMNS,
    }
    (model_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    with mlflow_client.start_run(run_name=spec.name, nested=True):
        mlflow_client.set_tags(
            {
                "project": "workforce-mlops",
                "stage": "compare_models",
                "model_name": spec.name,
                "model_kind": spec.kind,
            }
        )
        mlflow_client.log_params(
            {
                "model_name": spec.name,
                "model_kind": spec.kind,
                "hidden_dims": str(spec.hidden_dims),
                "epochs": int(train_cfg["epochs"]),
                "batch_size": int(train_cfg["batch_size"]),
                "lr": float(train_cfg["lr"]),
            }
        )
        for key, value in val_metrics.items():
            if np.isfinite(value):
                mlflow_client.log_metric(f"val_{key}", value)
        for key, value in test_metrics.items():
            if np.isfinite(value):
                mlflow_client.log_metric(f"test_{key}", value)
        mlflow_client.log_artifact(str(model_dir / "model.pt"))
        mlflow_client.log_artifact(str(model_dir / "metadata.json"))

    return {
        "model": spec.name,
        **{f"val_{k}": v for k, v in val_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
        "val_composite": (
            val_metrics["hiring_rmse"]
            + val_metrics["layoffs_rmse"]
            + val_metrics["volatility_rmse"]
        ),
    }


def run_model_comparison(
    input_path: str,
    params_path: str,
    output_report: str,
    output_summary: str,
    artifact_dir: str,
) -> pd.DataFrame:
    torch_mod, _, _, _ = require_torch()
    mlflow_client = get_configured_mlflow(default_experiment_name="workforce-model-comparison")

    params = yaml.safe_load(Path(params_path).read_text(encoding="utf-8"))
    train_cfg = params["training"]
    feat_cfg = params["features"]

    set_seed(int(train_cfg["seed"]))

    resolved_input = resolve_input_path(input_path)
    raw_df = pd.read_csv(resolved_input)

    processed = add_targets(raw_df, float(params["targets"]["layoff_risk_threshold"]))
    selected = DEFAULT_FEATURE_COLUMNS + [
        "target_hiring",
        "target_layoffs",
        "target_layoff_risk",
        "target_workforce_volatility",
    ]
    model_df = processed[selected].copy()

    train_df, val_df, test_df = split_by_time(model_df)

    numeric_cols = feat_cfg["numerical"]
    categorical_cols = feat_cfg["categorical"]
    feature_cols = categorical_cols + numeric_cols

    preprocessor = build_preprocessor(numeric_cols, categorical_cols)
    x_train = to_dense(preprocessor.fit_transform(train_df[feature_cols])).astype(np.float32)
    x_val = to_dense(preprocessor.transform(val_df[feature_cols])).astype(np.float32)
    x_test = to_dense(preprocessor.transform(test_df[feature_cols])).astype(np.float32)

    x_train_t = torch_mod.from_numpy(x_train)
    x_val_t = torch_mod.from_numpy(x_val)
    x_test_t = torch_mod.from_numpy(x_test)

    y_train_t = {k: torch_mod.from_numpy(v) for k, v in prepare_targets(train_df).items()}
    y_val_t = {k: torch_mod.from_numpy(v) for k, v in prepare_targets(val_df).items()}
    y_test_t = {k: torch_mod.from_numpy(v) for k, v in prepare_targets(test_df).items()}

    artifact_root = Path(artifact_dir)
    artifact_root.mkdir(parents=True, exist_ok=True)

    specs = [
        ModelSpec(name="baseline_mlp", kind="mlp", hidden_dims=[128, 64]),
        ModelSpec(name="wide_deep_mlp", kind="wide_deep", hidden_dims=[192, 96]),
        ModelSpec(name="residual_mlp", kind="residual", hidden_dims=[128]),
    ]

    with mlflow_client.start_run(run_name="model_comparison_pipeline"):
        mlflow_client.set_tags(
            {
                "project": "workforce-mlops",
                "stage": "compare_models",
            }
        )
        log_repro_context(mlflow_client)
        mlflow_client.log_params(
            {
                "input_path": str(resolved_input),
                "train_rows": int(len(train_df)),
                "val_rows": int(len(val_df)),
                "test_rows": int(len(test_df)),
                "num_models": len(specs),
            }
        )

        rows: list[dict[str, float]] = []
        for spec in specs:
            row = train_single_model(
                spec=spec,
                train_cfg=train_cfg,
                x_train_t=x_train_t,
                y_train_t=y_train_t,
                x_val_t=x_val_t,
                y_val_t=y_val_t,
                x_test_t=x_test_t,
                y_test_t=y_test_t,
                feature_columns=feature_cols,
                categorical_cols=categorical_cols,
                numeric_cols=numeric_cols,
                artifact_root=artifact_root,
                mlflow_client=mlflow_client,
            )
            rows.append(row)

        results = pd.DataFrame(rows).sort_values("val_composite", ascending=True).reset_index(
            drop=True
        )

        report_path = Path(output_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(report_path, index=False)

        summary = {
            "best_by_val_composite": results.iloc[0]["model"],
            "selection_metric": "val_composite",
            "models": results["model"].tolist(),
            "input_path": str(resolved_input),
            "train_rows": int(len(train_df)),
            "val_rows": int(len(val_df)),
            "test_rows": int(len(test_df)),
            "ranking": results[["model", "val_composite"]].to_dict(orient="records"),
        }

        summary_path = Path(output_summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        preprocessor_path = artifact_root / "shared_preprocessor.joblib"
        import joblib

        joblib.dump(preprocessor, preprocessor_path)

        mlflow_client.log_metric("best_val_composite", float(results.iloc[0]["val_composite"]))
        mlflow_client.log_artifact(str(report_path))
        mlflow_client.log_artifact(str(summary_path))
        mlflow_client.log_artifact(str(preprocessor_path))

        return results


def main() -> None:
    args = parse_args()

    results = run_model_comparison(
        input_path=args.input_path,
        params_path=args.params,
        output_report=args.output_report,
        output_summary=args.output_summary,
        artifact_dir=args.artifact_dir,
    )

    print(results.to_string(index=False))
    print(f"Saved report -> {args.output_report}")
    print(f"Saved summary -> {args.output_summary}")


if __name__ == "__main__":
    main()
