from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.metrics import f1_score, mean_absolute_error, mean_squared_error, roc_auc_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from workforce_mlops.config import TARGET_COLUMNS
from workforce_mlops.mlflow_utils import get_configured_mlflow

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
            "PyTorch is required for training. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    TORCH_MODULE = torch_mod
    NN_MODULE = nn_mod
    DATALOADER_MODULE = dataloader_mod
    TENSORDATASET_MODULE = tensor_dataset_mod
    return TORCH_MODULE, NN_MODULE, DATALOADER_MODULE, TENSORDATASET_MODULE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train multi-head workforce DNN")
    parser.add_argument("--train-path", required=True)
    parser.add_argument("--val-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--params", required=True)
    return parser.parse_args()


def set_seed(seed: int) -> None:
    torch_mod, _, _, _ = require_torch()
    np.random.seed(seed)
    torch_mod.manual_seed(seed)
    torch_mod.cuda.manual_seed_all(seed)


def build_preprocessor(numerical_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numerical_cols),
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


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    return rmse, mae


def evaluate(model: Any, x: Any, y: dict[str, Any]) -> dict[str, float]:
    torch_mod, _, _, _ = require_torch()
    model.eval()
    with torch_mod.no_grad():
        out = model(x)

    hiring_pred = out["hiring"].cpu().numpy()
    layoffs_pred = out["layoffs"].cpu().numpy()
    risk_logits = out["layoff_risk_logits"].cpu().numpy()
    vol_pred = out["workforce_volatility"].cpu().numpy()

    # Clip logits to avoid overflow warnings in exp for extreme values.
    risk_prob = 1.0 / (1.0 + np.exp(-np.clip(risk_logits, -60.0, 60.0)))
    risk_label = (risk_prob >= 0.5).astype(int)

    hiring_rmse, hiring_mae = regression_metrics(y["hiring"].cpu().numpy(), hiring_pred)
    layoffs_rmse, layoffs_mae = regression_metrics(y["layoffs"].cpu().numpy(), layoffs_pred)
    vol_rmse, vol_mae = regression_metrics(y["workforce_volatility"].cpu().numpy(), vol_pred)

    risk_true = y["layoff_risk"].cpu().numpy().astype(int)
    try:
        risk_auc = float(roc_auc_score(risk_true, risk_prob))
    except ValueError:
        risk_auc = float("nan")
    risk_f1 = float(f1_score(risk_true, risk_label, zero_division=0))

    return {
        "hiring_rmse": hiring_rmse,
        "hiring_mae": hiring_mae,
        "layoffs_rmse": layoffs_rmse,
        "layoffs_mae": layoffs_mae,
        "volatility_rmse": vol_rmse,
        "volatility_mae": vol_mae,
        "layoff_risk_auc": risk_auc,
        "layoff_risk_f1": risk_f1,
    }


def main() -> None:
    args = parse_args()
    torch_mod, nn, DataLoader, TensorDataset = require_torch()
    params = yaml.safe_load(Path(args.params).read_text(encoding="utf-8"))

    train_cfg = params["training"]
    feat_cfg = params["features"]

    set_seed(int(train_cfg["seed"]))

    train_df = pd.read_csv(args.train_path)
    val_df = pd.read_csv(args.val_path)

    numerical_cols = feat_cfg["numerical"]
    categorical_cols = feat_cfg["categorical"]
    feature_cols = categorical_cols + numerical_cols

    preprocessor = build_preprocessor(numerical_cols, categorical_cols)

    x_train = preprocessor.fit_transform(train_df[feature_cols])
    x_val = preprocessor.transform(val_df[feature_cols])

    x_train_np = to_dense(x_train).astype(np.float32)
    x_val_np = to_dense(x_val).astype(np.float32)

    y_train_np = prepare_targets(train_df)
    y_val_np = prepare_targets(val_df)

    x_train_t = torch_mod.from_numpy(x_train_np)
    x_val_t = torch_mod.from_numpy(x_val_np)

    y_train_t = {k: torch_mod.from_numpy(v) for k, v in y_train_np.items()}
    y_val_t = {k: torch_mod.from_numpy(v) for k, v in y_val_np.items()}

    dataset = TensorDataset(
        x_train_t,
        y_train_t["hiring"],
        y_train_t["layoffs"],
        y_train_t["layoff_risk"],
        y_train_t["workforce_volatility"],
    )

    loader = DataLoader(dataset, batch_size=int(train_cfg["batch_size"]), shuffle=True)

    from workforce_mlops.models.multitask_model import MultiTaskNet

    model = MultiTaskNet(
        input_dim=x_train_t.shape[1],
        hidden_dims=[int(v) for v in train_cfg["hidden_dims"]],
        dropout=float(train_cfg["dropout"]),
    )

    mse_loss = nn.MSELoss()
    bce_loss = nn.BCEWithLogitsLoss()

    optimizer = torch_mod.optim.Adam(
        model.parameters(),
        lr=float(train_cfg["lr"]),
        weight_decay=float(train_cfg["weight_decay"]),
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    Path("reports").mkdir(parents=True, exist_ok=True)

    mlflow = get_configured_mlflow(default_experiment_name="workforce-multitask")

    best_val = float("inf")
    best_state = None
    patience = int(train_cfg["early_stopping_patience"])
    patience_counter = 0

    weights = train_cfg["loss_weights"]

    with mlflow.start_run(run_name="multitask-dnn"):
        mlflow.set_tags({"project": "workforce-mlops", "model_type": "multitask-dnn"})
        mlflow.log_params(
            {
                "epochs": int(train_cfg["epochs"]),
                "batch_size": int(train_cfg["batch_size"]),
                "lr": float(train_cfg["lr"]),
                "weight_decay": float(train_cfg["weight_decay"]),
                "hidden_dims": str(train_cfg["hidden_dims"]),
                "dropout": float(train_cfg["dropout"]),
            }
        )

        for epoch in range(int(train_cfg["epochs"])):
            model.train()
            total_loss = 0.0

            for batch in loader:
                x_b, y_h, y_l, y_r, y_v = batch
                out = model(x_b)

                loss_h = mse_loss(out["hiring"], y_h)
                loss_l = mse_loss(out["layoffs"], y_l)
                loss_r = bce_loss(out["layoff_risk_logits"], y_r)
                loss_v = mse_loss(out["workforce_volatility"], y_v)

                loss = (
                    float(weights["hiring"]) * loss_h
                    + float(weights["layoffs"]) * loss_l
                    + float(weights["layoff_risk"]) * loss_r
                    + float(weights["workforce_volatility"]) * loss_v
                )

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                total_loss += float(loss.item())

            val_metrics = evaluate(model, x_val_t, y_val_t)
            val_score = (
                val_metrics["hiring_rmse"]
                + val_metrics["layoffs_rmse"]
                + val_metrics["volatility_rmse"]
            )

            mlflow.log_metric("train_loss", total_loss / max(len(loader), 1), step=epoch)
            for k, v in val_metrics.items():
                if np.isfinite(v):
                    mlflow.log_metric(f"val_{k}", v, step=epoch)

            if val_score < best_val:
                best_val = val_score
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                break

        if best_state is None:
            best_state = model.state_dict()

        model.load_state_dict(best_state)

        model_path = output_dir / "model.pt"
        prep_path = output_dir / "preprocessor.joblib"
        meta_path = output_dir / "metadata.json"
        val_metrics_path = Path("reports/val_metrics.json")

        torch_mod.save(model.state_dict(), model_path)
        joblib.dump(preprocessor, prep_path)

        metadata = {
            "model_name": "baseline_mlp",
            "model_kind": "mlp",
            "feature_columns": feature_cols,
            "categorical_columns": categorical_cols,
            "numerical_columns": numerical_cols,
            "target_columns": TARGET_COLUMNS,
            "input_dim": int(x_train_t.shape[1]),
            "hidden_dims": [int(v) for v in train_cfg["hidden_dims"]],
            "dropout": float(train_cfg["dropout"]),
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        final_val_metrics = evaluate(model, x_val_t, y_val_t)
        val_metrics_path.write_text(json.dumps(final_val_metrics, indent=2), encoding="utf-8")

        mlflow.log_artifact(str(model_path))
        mlflow.log_artifact(str(prep_path))
        mlflow.log_artifact(str(meta_path))
        mlflow.log_artifact(str(val_metrics_path))

    print(f"Training complete. Artifacts saved in {output_dir}")


if __name__ == "__main__":
    main()
