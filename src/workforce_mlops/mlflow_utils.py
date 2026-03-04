from __future__ import annotations

import os
from pathlib import Path


def get_configured_mlflow(default_experiment_name: str):
    try:
        import mlflow  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "MLflow is required but not installed. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    else:
        local_store = Path.cwd() / "mlruns"
        mlflow.set_tracking_uri(local_store.resolve().as_uri())

    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", default_experiment_name)
    mlflow.set_experiment(experiment_name)
    return mlflow
