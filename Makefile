.PHONY: install lint test repro train evaluate app

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

lint:
	PYTHONPATH=src ruff check src tests app

test:
	PYTHONPATH=src pytest -q

repro:
	PYTHONPATH=src dvc repro

train:
	OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python -m workforce_mlops.models.train \
		--train-path data/processed/train.csv \
		--val-path data/processed/val.csv \
		--output-dir artifacts/model \
		--params params.yaml

evaluate:
	PYTHONPATH=src python -m workforce_mlops.models.evaluate \
		--test-path data/processed/test.csv \
		--artifact-dir artifacts/model \
		--report-path reports/test_metrics.json

app:
	PYTHONPATH=src streamlit run app/streamlit_app.py
