from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from workforce_mlops.api.presets import ScenarioPreset, build_presets
from workforce_mlops.api.schemas import PredictionResponse, PredictionValues
from workforce_mlops.api.services.scenario import features_from_market_index, simulate_forecast
from workforce_mlops.models.predict import load_assets, load_model


def require_torch():
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyTorch is required for prediction service. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return torch


class PredictionService:
    def __init__(self, project_root: Path, artifact_dir: Path | None = None) -> None:
        self.project_root = project_root
        self.artifact_dir = artifact_dir or (project_root / "artifacts" / "model")

        if not self.artifact_dir.exists():
            raise FileNotFoundError(f"Model artifacts not found: {self.artifact_dir}")

        self.preprocessor, self.metadata = load_assets(self.artifact_dir)
        self.model = None
        self.torch_runtime_error = self._probe_torch_runtime()
        self.feature_columns: list[str] = list(self.metadata["feature_columns"])

        self.default_company = self._load_default_company()
        self.base_year = datetime.utcnow().year + 1
        self.presets = build_presets(default_company=self.default_company, base_year=self.base_year)

    def _probe_torch_runtime(self) -> str | None:
        probe = subprocess.run(
            [sys.executable, "-c", "import torch; print(torch.__version__)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return None

        details = (probe.stderr or probe.stdout).strip().splitlines()
        reason = details[-1] if details else "unknown runtime error"
        return (
            "PyTorch runtime is not usable in this environment. "
            "Reinstall a compatible torch wheel for your OS/Python. "
            f"Runtime detail: {reason}"
        )

    def _ensure_model_loaded(self) -> None:
        if self.model is not None:
            return

        if self.torch_runtime_error is not None:
            raise RuntimeError(self.torch_runtime_error)

        self.model = load_model(self.artifact_dir, self.metadata)

    def _load_default_company(self) -> str:
        candidate_paths = [
            self.project_root / "data" / "raw" / "workforce.csv",
            self.project_root / "data" / "interim" / "workforce_clean.csv",
            self.project_root / "data" / "processed" / "train.csv",
        ]
        for path in candidate_paths:
            if path.exists():
                df = pd.read_csv(path, usecols=["company"])
                if not df.empty:
                    return str(df["company"].dropna().astype(str).iloc[0])
        return "ExampleCorp"

    def list_presets(self) -> list[ScenarioPreset]:
        return list(self.presets.values())

    def predict_from_preset(self, preset_id: str) -> PredictionResponse:
        preset = self.presets.get(preset_id)
        if preset is None:
            valid = ", ".join(sorted(self.presets.keys()))
            raise ValueError(f"Unknown preset_id '{preset_id}'. Valid values: {valid}")

        index_hint = {
            "aggressive_expansion": 85.0,
            "cost_cut_recession": 15.0,
            "automation_transition": 55.0,
        }.get(preset_id, 50.0)

        return self._predict(
            scenario_id=preset.id,
            scenario_name=preset.name,
            scenario_description=preset.description,
            features=dict(preset.features),
            market_index=index_hint,
        )

    def predict_from_custom_market(self, market_index: float) -> PredictionResponse:
        features = features_from_market_index(
            default_company=self.default_company,
            market_index=market_index,
            year=self.base_year,
        )

        return self._predict(
            scenario_id="custom_market_index",
            scenario_name="Custom Market Index",
            scenario_description=(
                "Custom scenario generated from one user-controlled market index input "
                "(0=recession, 100=expansion)."
            ),
            features=features,
            market_index=market_index,
        )

    def _predict(
        self,
        scenario_id: str,
        scenario_name: str,
        scenario_description: str,
        features: dict[str, float | int | str],
        market_index: float,
    ) -> PredictionResponse:
        self._ensure_model_loaded()
        torch = require_torch()
        ordered_features = {k: features[k] for k in self.feature_columns}

        x = self.preprocessor.transform(pd.DataFrame([ordered_features]))
        if hasattr(x, "toarray"):
            x = x.toarray()

        x_t = torch.from_numpy(np.asarray(x, dtype=np.float32))
        with torch.no_grad():
            out = self.model(x_t)

        pred_hiring = float(out["hiring"].numpy()[0])
        pred_layoffs = float(out["layoffs"].numpy()[0])
        pred_risk = float(torch.sigmoid(out["layoff_risk_logits"])[0].numpy())
        pred_volatility = float(out["workforce_volatility"].numpy()[0])

        predictions = PredictionValues(
            hiring=pred_hiring,
            layoffs=pred_layoffs,
            layoff_risk_prob=float(np.clip(pred_risk, 0.0, 1.0)),
            workforce_volatility=pred_volatility,
        )

        forecast = simulate_forecast(
            year=int(features["year"]),
            employees_start=float(features["employees_start"]),
            pred_hiring=pred_hiring,
            pred_layoffs=pred_layoffs,
            pred_risk=pred_risk,
            pred_volatility=pred_volatility,
            market_index=market_index,
            horizon=6,
        )

        return PredictionResponse(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            scenario_description=scenario_description,
            features=ordered_features,
            predictions=predictions,
            forecast=forecast,
        )
