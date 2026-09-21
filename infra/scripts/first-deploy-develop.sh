#!/usr/bin/env bash
# One-time first deploy of envs/develop from an admin workstation.
#
# ECS services need images in ECR, and ECR is created by this same stack, so
# the first deploy runs in three steps: ECR and CI resources, then the images,
# then everything else. After this, pushes to main deploy through GitHub Actions
# once the repository variables printed at the end are set.
#
# Prerequisites: infra/bootstrap applied; AWS credentials with admin rights;
# Docker with buildx. Usage: AWS_PROFILE=<profile> infra/scripts/first-deploy-develop.sh
set -euo pipefail

export AWS_REGION="${AWS_REGION:-ap-northeast-2}"
ROOT="$(git rev-parse --show-toplevel)"
SHA="$(git -C "$ROOT" rev-parse HEAD)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="onboarding-tfstate-${ACCOUNT}"
VARS=(-var "state_bucket_name=${BUCKET}" -var "image_tag=${SHA}")

cd "$ROOT/infra/envs/develop"
terraform init -input=false -backend-config="bucket=${BUCKET}"

echo "==> 1/3 ECR repositories, GitHub OIDC provider, deploy role"
terraform apply -input=false "${VARS[@]}" -target=module.ci

echo "==> 2/3 images tagged ${SHA} (ECS runs X86_64)"
REGISTRY="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
for service in backend mock frontend; do
  repo="$(terraform output -json ecr_repository_urls | python3 -c "import json,sys; print(json.load(sys.stdin)['${service}'])")"
  docker buildx build --platform linux/amd64 -t "${repo}:${SHA}" --push "$ROOT/${service}"
done

echo "==> 3/3 everything else"
terraform apply -input=false "${VARS[@]}"

echo
echo "Set these GitHub repository variables (Settings > Secrets and variables > Actions > Variables):"
echo "  AWS_DEPLOY_ROLE_ARN_DEVELOP = $(terraform output -raw deploy_role_arn)"
echo "  TF_STATE_BUCKET             = ${BUCKET}"
echo "Open: $(terraform output -raw base_url)"
