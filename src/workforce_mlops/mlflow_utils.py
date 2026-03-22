from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _maybe_prompt_tracking_uri() -> str | None:
    if os.getenv("MLFLOW_TRACKING_URI"):
        return os.getenv("MLFLOW_TRACKING_URI")

    if os.getenv("WORKFORCE_PROMPT", "1") != "1":
        return None

    if not sys.stdin.isatty():
        return None

    try:
        value = input(
            "Enter MLflow Tracking URI (leave blank to use local mlruns): "
        ).strip()
    except EOFError:
        return None

    if not value:
        return None

    os.environ["MLFLOW_TRACKING_URI"] = value
    return value


def get_configured_mlflow(default_experiment_name: str):
    try:
        import mlflow  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "MLflow is required but not installed. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI") or _maybe_prompt_tracking_uri()
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    else:
        local_store = Path.cwd() / "mlruns"
        mlflow.set_tracking_uri(local_store.resolve().as_uri())

    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", default_experiment_name)
    mlflow.set_experiment(experiment_name)
    return mlflow


def _get_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        sha = result.stdout.strip()
        return sha or None
    except (OSError, subprocess.CalledProcessError):
        return None


def log_repro_context(
    mlflow: Any,
    params_path: str | Path = "params.yaml",
    dvc_lock_path: str | Path = "dvc.lock",
    extra_tags: dict[str, str] | None = None,
) -> None:
    tags: dict[str, str] = {}
    sha = _get_git_sha()
    if sha:
        tags["git_sha"] = sha
    if extra_tags:
        tags.update({k: str(v) for k, v in extra_tags.items()})
    if tags:
        mlflow.set_tags(tags)

    for path in (params_path, dvc_lock_path):
        path = Path(path)
        if path.exists():
            mlflow.log_artifact(str(path))
