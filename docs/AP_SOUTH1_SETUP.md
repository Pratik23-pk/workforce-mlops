# AWS ap-south-1 Setup for Workforce MLOps CD/GitOps

This project now uses **ap-south-1** (Mumbai) region for ECR, S3, and other AWS resources.

## Required Setup Steps

### 1️⃣ Create AWS Resources in ap-south-1

```bash
export AWS_REGION='ap-south-1'
export AWS_ACCOUNT_ID='357457230342'  # Replace with your account ID

# Create DVC S3 bucket
aws s3 mb s3://workforce-mlops-dvc-${AWS_ACCOUNT_ID} \
  --region ${AWS_REGION}

# Create MLflow S3 bucket  
aws s3 mb s3://workforce-mlops-mlflow-${AWS_ACCOUNT_ID} \
  --region ${AWS_REGION}

# Create ECR repository
aws ecr create-repository \
  --repository-name workforce-mlops-app \
  --region ${AWS_REGION} \
  --encryption-configuration encryptionType=AES

echo "✓ AWS resources created in ap-south-1"
```

### 2️⃣ Set Up IAM OIDC Provider (if not already done)

```bash
# Create OIDC provider for GitHub Actions
OIDC_PROVIDER_ARN=$(aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --query 'OpenIDConnectProviderArn' \
  --output text 2>/dev/null || echo "Already exists")

echo "OIDC Provider: $OIDC_PROVIDER_ARN"
```

### 3️⃣ Create IAM Role for GitHub Actions

This role is assumed by GitHub Actions workflows for S3 + ECR access.

```bash
export GITHUB_REPO='Pratik23-pk/workforce-mlops'  # Replace with your repo

# Create trust policy
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::357457230342:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:Pratik23-pk/workforce-mlops:*"
        }
      }
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name GitHubActionsWorkforceGitOpsRole \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  --region ap-south-1 2>/dev/null || echo "Role may already exist"

# Create inline policy for S3 + ECR + DVC
cat > /tmp/policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::workforce-mlops-dvc-357457230342",
        "arn:aws:s3:::workforce-mlops-dvc-357457230342/*",
        "arn:aws:s3:::workforce-mlops-mlflow-357457230342",
        "arn:aws:s3:::workforce-mlops-mlflow-357457230342/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:ap-south-1:357457230342:repository/workforce-mlops-app"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name GitHubActionsWorkforceGitOpsRole \
  --policy-name GitHubActionsWorkforcePolicy \
  --policy-document file:///tmp/policy.json

echo "✓ IAM role configured"
```

### 4️⃣ Set GitHub Actions Secrets

Set these in your GitHub repo: **Settings → Secrets and variables → Actions**

```bash
# Required secrets (use values from infra/aws_gitops_outputs.env)
AWS_ROLE_TO_ASSUME=arn:aws:iam::357457230342:role/GitHubActionsWorkforceGitOpsRole
AWS_REGION=ap-south-1
ECR_REPOSITORY=workforce-mlops-app
DVC_S3_BUCKET=workforce-mlops-dvc-357457230342
MLFLOW_TRACKING_URI=<your-mlflow-server-uri>  # e.g., http://mlflow.example.com

# Optional MLflow secrets
MLFLOW_EXPERIMENT_NAME=workforce-multitask
MLFLOW_TRACKING_USERNAME=<if-using-authentication>
MLFLOW_TRACKING_PASSWORD=<if-using-authentication>
```

**Quick setup with CLI:**
```bash
source infra/aws_gitops_outputs.env
gh secret set AWS_ROLE_TO_ASSUME -b "${AWS_ROLE_TO_ASSUME}"
gh secret set AWS_REGION -b "ap-south-1"
gh secret set ECR_REPOSITORY -b "${ECR_REPOSITORY}"
gh secret set DVC_S3_BUCKET -b "${DVC_S3_BUCKET}"
# ... add others similarly
```

### 5️⃣ Push Local DVC Artifacts to S3

Before first CD trigger, push your local artifacts:

```bash
dvc remote add -f origin "s3://workforce-mlops-dvc-357457230342/dvc"
dvc remote modify origin region "ap-south-1"
dvc push -v -j 1
```

### 6️⃣ Verify Setup

```bash
# Run verification script
bash scripts/verify_dvc_s3.sh

# Check GitHub Actions workflow
git push  # This should trigger CD workflow
# Monitor in GitHub repo → Actions tab
```

## Troubleshooting

### DVC Pull Fails in CD

1. **"Access Denied" errors**
   - Verify `AWS_ROLE_TO_ASSUME` is correct
   - Check IAM role has `s3:GetObject` + `s3:ListBucket` permissions
   - Confirm DVC_S3_BUCKET name matches exactly

2. **"NoSuchBucket" errors**
   - S3 bucket doesn't exist in ap-south-1
   - Create it: `aws s3 mb s3://workforce-mlops-dvc-357457230342 --region ap-south-1`

3. **"InvalidRegionError"**
   - Ensure AWS_REGION=ap-south-1 in GitHub secrets
   - Verify all resources are in ap-south-1 (not us-east-1)

### ECR Push Fails

1. Check ECR repo exists: `aws ecr describe-repositories --region ap-south-1`
2. Verify IAM role has ECR permissions
3. Ensure Docker is authenticating to correct registry: `357457230342.dkr.ecr.ap-south-1.amazonaws.com`

## Files Modified

- `infra/aws_gitops_outputs.env` → uses ap-south-1
- `deploy/k8s/overlays/prod/kustomization.yaml` → ECR registry updated to ap-south-1
- `.github/workflows/cd.yml` → AWS credentials + DVC pull fixed for ap-south-1
- All scripts updated to default to ap-south-1

## Region Info

**Mumbai (ap-south-1)** selected for:
- Lower latency from India
- Cost optimization
- Regional compliance if needed

To change back to us-east-1: Update scripts + `.env.example` → set all references to `us-east-1`
