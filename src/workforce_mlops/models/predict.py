from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

TORCH_MODULE = None


def require_torch():
    global TORCH_MODULE

    if TORCH_MODULE is not None:
        return TORCH_MODULE

    try:
        import torch as torch_mod
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyTorch is required for model inference. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    TORCH_MODULE = torch_mod
    return TORCH_MODULE


def load_assets(artifact_dir: str | Path):
    artifact_dir = Path(artifact_dir)
    metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
    preprocessor = joblib.load(artifact_dir / "preprocessor.joblib")
    return preprocessor, metadata


def load_model(artifact_dir: str | Path, metadata: dict):
    torch_mod = require_torch()
    from workforce_mlops.models.model_factory import build_model

    hidden_dims: Any = metadata.get("hidden_dims", [128, 64])
    if isinstance(hidden_dims, str):
        hidden_dims = json.loads(hidden_dims)

    model = build_model(
        model_kind=str(metadata.get("model_kind", "mlp")),
        input_dim=int(metadata["input_dim"]),
        hidden_dims=[int(v) for v in hidden_dims],
        dropout=float(metadata.get("dropout", 0.2)),
    )

    state = torch_mod.load(artifact_dir / "model.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


def load_bundle(artifact_dir: str | Path):
    artifact_dir = Path(artifact_dir)
    preprocessor, metadata = load_assets(artifact_dir)
    model = load_model(artifact_dir, metadata)
    return model, preprocessor, metadata


def predict_df(df: pd.DataFrame, artifact_dir: str | Path) -> pd.DataFrame:
    torch_mod = require_torch()
    model, preprocessor, metadata = load_bundle(artifact_dir)

    x = preprocessor.transform(df[metadata["feature_columns"]])
    if hasattr(x, "toarray"):
        x = x.toarray()

    x_t = torch_mod.from_numpy(np.asarray(x, dtype=np.float32))

    with torch_mod.no_grad():
        out = model(x_t)

    risk_prob = torch_mod.sigmoid(out["layoff_risk_logits"]).numpy()

    pred_df = pd.DataFrame(
        {
            "pred_hiring": out["hiring"].numpy(),
            "pred_layoffs": out["layoffs"].numpy(),
            "pred_layoff_risk_prob": risk_prob,
            "pred_workforce_volatility": out["workforce_volatility"].numpy(),
        }
    )
    return pred_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch predict from CSV")
    parser.add_argument("--input", required=True, help="Input features CSV")
    parser.add_argument("--artifact-dir", required=True, help="Model artifact directory")
    parser.add_argument("--output", required=True, help="Predictions CSV output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    pred = predict_df(df, args.artifact_dir)
    pred.to_csv(args.output, index=False)
    print(f"Saved predictions -> {args.output}")


if __name__ == "__main__":
    main()
