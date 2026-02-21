# Troubleshooting

## DVC error: `cannot import name '_DIR_MARK' from pathspec.patterns.gitwildmatch`

Cause: incompatible `pathspec` major version.

Fix:

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
pip uninstall -y pathspec
pip install pathspec==0.12.1
pip install -r requirements.txt
```

Verify:

```bash
python -c "import pathspec; print(pathspec.__version__)"
dvc version
```

Expected pathspec version: `0.12.1`

## DVC error: `sqlite3.OperationalError: unable to open database file`

Cause: DVC site cache path is not writable.

Fix:

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
mkdir -p .dvc/site-cache
dvc config core.site_cache_dir .dvc/site-cache
dvc status
```

## DVC push error: `Unable to locate credentials`

Cause: AWS credentials are not available to DVC/s3fs.

Fix:

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate

aws sts get-caller-identity
# if this fails, run aws configure or export AWS_PROFILE

export AWS_REGION="us-east-1"
export DVC_S3_BUCKET="<your-dvc-bucket>"
export AWS_PROFILE="default"  # optional

bash scripts/setup_dvc_s3.sh
dvc push -v -j 1
```

## AWS CLI error: `Could not connect to the endpoint URL`

Cause: network path to AWS endpoint is blocked.

Fix:

- Check internet and corporate VPN/proxy constraints.
- Verify region endpoint connectivity:

```bash
curl -I https://sts.us-east-1.amazonaws.com/
aws sts get-caller-identity --region us-east-1
```

## DVC push error: `AccessDenied` or `403`

Cause: IAM identity does not have S3 permissions for the DVC bucket.

Fix:

- Ensure your IAM user/role has `s3:ListBucket`, `s3:GetObject`, `s3:PutObject` on the DVC bucket and prefix.
- Re-run:

```bash
aws sts get-caller-identity
dvc push -v -j 1
```

## Migrating from old DagsHub remote to AWS S3 remote

If your repo previously used DagsHub, reset remote config before pushing:

```bash
cd /Users/pratikkanjilal/Documents/workforce-mlops
source .venv/bin/activate
rm -f .dvc/config.local
export AWS_REGION="us-east-1"
export DVC_S3_BUCKET="<your-dvc-bucket>"
bash scripts/setup_dvc_s3.sh
dvc push -v -j 1
```

## Training warning: `RuntimeWarning: overflow encountered in exp`

Status: already handled in training code by clipping logits before sigmoid probability conversion.
