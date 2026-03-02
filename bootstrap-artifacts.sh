#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# bootstrap-artifacts.sh
#
# Uploads a minimal placeholder.zip to the deployment artifacts S3 bucket.
# Run this ONCE before the first `deploy-cfn.sh <env> create`.
#
# Usage:
#   ./bootstrap-artifacts.sh <environment>
#
# The bucket must already exist. The stack creates it, so this script handles
# the chicken-and-egg problem by creating the bucket directly if needed.
# -----------------------------------------------------------------------------

ENVIRONMENT="${1:-}"
[[ -n "$ENVIRONMENT" ]] || { echo "Usage: $0 <environment>" >&2; exit 2; }

APPLICATION="${APPLICATION:-acsauth}"
BUCKET_NAME="${APPLICATION}-${ENVIRONMENT}-deployment-artifacts"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ca-central-1}}"

echo "Ensuring bucket exists: ${BUCKET_NAME}"
if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$AWS_REGION" \
    --create-bucket-configuration LocationConstraint="$AWS_REGION"
  echo "Created bucket: ${BUCKET_NAME}"
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Create a minimal valid zip with a dummy file
echo "placeholder" > "$TMPDIR/placeholder.txt"
(cd "$TMPDIR" && zip -q placeholder.zip placeholder.txt)

echo "Uploading placeholder.zip to s3://${BUCKET_NAME}/"
aws s3 cp "$TMPDIR/placeholder.zip" "s3://${BUCKET_NAME}/placeholder.zip" --region "$AWS_REGION"

echo "Done. You can now run: ./deploy-cfn.sh ${ENVIRONMENT} create"
