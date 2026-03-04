.PHONY: install lint test repro train evaluate compare-models promote-model ct-auto app app-dev clean-local

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

lint:
	PYTHONPATH=src ruff check src tests

test:
	PYTHONPATH=src pytest -q

repro:
	PYTHONPATH=src dvc repro

train:
	OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python -m workforce_mlops.models.train \
		--train-path data/processed/train.csv \
		--val-path data/processed/val.csv \
		--output-dir artifacts/baseline_model \
		--params params.yaml

evaluate:
	PYTHONPATH=src python -m workforce_mlops.models.evaluate \
		--test-path data/processed/test.csv \
		--artifact-dir artifacts/model \
		--report-path reports/test_metrics.json

compare-models:
	PYTHONPATH=src python -m workforce_mlops.models.compare_models \
		--input-path data/interim/workforce_clean.csv \
		--params params.yaml \
		--output-report reports/model_comparison.csv \
		--output-summary reports/model_comparison_summary.json \
		--artifact-dir artifacts/experiments

promote-model:
	PYTHONPATH=src python -m workforce_mlops.models.promote_model \
		--comparison-report reports/model_comparison.csv \
		--summary-path reports/model_comparison_summary.json \
		--experiments-dir artifacts/experiments \
		--output-dir artifacts/model \
		--params params.yaml \
		--promotion-report reports/model_promotion.json

ct-auto:
	OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src dvc repro compare_models promote_model evaluate

app:
	PYTHONPATH=src uvicorn workforce_mlops.api.main:app --host 0.0.0.0 --port 8000

app-dev:
	PYTHONPATH=src uvicorn workforce_mlops.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src --reload-exclude ".venv/*"

clean-local:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
