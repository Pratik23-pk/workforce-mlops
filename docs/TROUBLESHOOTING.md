# Troubleshooting

Use `<repo-root>` as your local project directory.

Activate environment first:

- macOS/Linux:

```bash
cd <repo-root>
source .venv/bin/activate
```

- Windows PowerShell:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\Activate.ps1
```

## `ModuleNotFoundError: No module named 'workforce_mlops'`

Cause: `src/` package path is not available in current shell/notebook kernel.

Fix:

```bash
cd <repo-root>
source .venv/bin/activate
export PYTHONPATH=src
pip install -e .
```

PowerShell equivalent:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
pip install -e .
```

In VS Code notebook, select kernel from this project `.venv`.

## `ModuleNotFoundError: No module named 'seaborn'` or `mlflow`

Cause: missing dependencies in the active environment.

Fix:

```bash
cd <repo-root>
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## DVC error: `cannot import name '_DIR_MARK' from pathspec.patterns.gitwildmatch`

Cause: incompatible `pathspec` version.

Fix:

```bash
cd <repo-root>
source .venv/bin/activate
pip uninstall -y pathspec
pip install pathspec==0.12.1
pip install -r requirements.txt
```

## DVC push error: `Unable to locate credentials`

Cause: AWS credentials unavailable for DVC/s3fs.

Fix:

```bash
aws sts get-caller-identity
# if this fails: configure credentials in AWS Console/CLI profile first

cd <repo-root>
source .venv/bin/activate
export AWS_REGION=us-east-1
export DVC_S3_BUCKET=<your-dvc-bucket>
bash scripts/setup_dvc_s3.sh
dvc push -v -j 1
```

## DVC push error: `AccessDenied` / `403`

Cause: IAM permissions missing on the DVC S3 bucket.

Required actions:

- `s3:ListBucket` on `arn:aws:s3:::<bucket>`
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `arn:aws:s3:::<bucket>/*`

## API error: `Model artifacts not found at artifacts/model`

Cause: model artifacts have not been produced/pulled.

Fix:

```bash
cd <repo-root>
source .venv/bin/activate
export PYTHONPATH=src
dvc repro
dvc pull
```

PowerShell equivalent:

```powershell
Set-Location <repo-root>
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
dvc repro
dvc pull
```

## Notebook runs but training cell fails (torch runtime issue)

If your environment has PyTorch runtime issues, EDA/preprocessing cells should still work.

Use this to run only non-torch tests:

```bash
cd <repo-root>
source .venv/bin/activate
PYTHONPATH=src pytest -q
```

Run torch test explicitly when your runtime is stable:

```bash
RUN_TORCH_TESTS=1 PYTHONPATH=src pytest -q tests/test_model_forward.py
```

## API prediction returns `503` with `PyTorch runtime is not usable`

Cause: Torch installation exists but native runtime is broken for current OS/Python build.

Fix:

```bash
cd <repo-root>
source .venv/bin/activate
python -V   # must be 3.11 or 3.12
pip uninstall -y torch
pip install --no-cache-dir -r requirements.txt
python -c "import torch; print(torch.__version__)"
```

If import still fails, recreate the virtual environment with a supported Python and reinstall:

```bash
cd <repo-root>
rm -rf .venv
bash scripts/create_venv.sh
source .venv/bin/activate
pip install -r requirements.txt
```

## Argo CD not deploying new image

Check:

1. `.github/workflows/cd.yml` succeeded.
2. `deploy/k8s/overlays/prod/kustomization.yaml` was updated with new tag.
3. Argo CD app is `Synced` and `Healthy`.

Commands:

```bash
kubectl -n argocd get applications
kubectl -n workforce-mlops get deploy,svc,pods
```
