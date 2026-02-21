from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from workforce_mlops.models.multitask_model import MultiTaskNet


def load_bundle(artifact_dir: str | Path):
    artifact_dir = Path(artifact_dir)
    metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
    preprocessor = joblib.load(artifact_dir / "preprocessor.joblib")

    model = MultiTaskNet(
        input_dim=int(metadata["input_dim"]),
        hidden_dims=[int(v) for v in metadata["hidden_dims"]],
        dropout=float(metadata["dropout"]),
    )

    state = torch.load(artifact_dir / "model.pt", map_location="cpu")
    model.load_state_dict(state)
    model.eval()

    return model, preprocessor, metadata


def predict_df(df: pd.DataFrame, artifact_dir: str | Path) -> pd.DataFrame:
    model, preprocessor, metadata = load_bundle(artifact_dir)

    x = preprocessor.transform(df[metadata["feature_columns"]])
    if hasattr(x, "toarray"):
        x = x.toarray()

    x_t = torch.from_numpy(np.asarray(x, dtype=np.float32))

    with torch.no_grad():
        out = model(x_t)

    risk_prob = torch.sigmoid(out["layoff_risk_logits"]).numpy()

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
