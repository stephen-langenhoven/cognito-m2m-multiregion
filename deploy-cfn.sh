#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# deploy-cfn.sh
#
# Usage:
#   ./deploy-cfn.sh <environment> <create|update>
#
# Examples:
#   ./deploy-cfn.sh dev create
#   ./deploy-cfn.sh prod update
#
# Expectations:
# - AWS CLI configured (or AWS_PROFILE/AWS_REGION exported)
# - A template file exists at ./cloudformation/main.yaml (configurable below)
# - Optional parameter files at ./params/<env>.json or ./params/<env>.properties
# -----------------------------------------------------------------------------

ENVIRONMENT="${1:-}"
MODE="${2:-}"

# ---- Configuration (edit to match your repo conventions) ---------------------
TEMPLATE_FILE="${TEMPLATE_FILE:-cognito-m2m-stack.yaml}"
PARAMS_JSON_FILE="${PARAMS_JSON_FILE:-./params/${ENVIRONMENT}.json}"          # CloudFormation Parameters JSON
PARAMS_PROPS_FILE="${PARAMS_PROPS_FILE:-./params/${ENVIRONMENT}.properties}"  # key=value lines (alternate)
TAGS_FILE="${TAGS_FILE:-./tags/${ENVIRONMENT}.properties}"                    # key=value lines (optional)

STACK_PREFIX="${STACK_PREFIX:-acsauth}"   # used to form stack name
STACK_NAME="${STACK_PREFIX}-${ENVIRONMENT}"

AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ca-central-1}}"

# CAPABILITY_NAMED_IAM is common; add AUTO_EXPAND if using transforms/macros
CAPABILITIES=(CAPABILITY_NAMED_IAM)

# Optional: role used by CloudFormation execution
CFN_ROLE_ARN="${CFN_ROLE_ARN:-}"  # e.g., arn:aws:iam::<acct>:role/<role-name>

# Optional: extra args you may want to pass, e.g. "--profile myprofile"
AWS_CLI_EXTRA_ARGS=(${AWS_CLI_EXTRA_ARGS:-})

# ---- Helpers ----------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
  cat >&2 <<EOF
Usage:
  $0 <environment> <create|update>

Environment:
  A short name like dev, qa, staging, prod

Mode:
  create  - creates the stack (fails if it already exists)
  update  - updates the stack (fails if it does not exist)

Config via env vars:
  TEMPLATE_FILE, STACK_PREFIX, AWS_REGION, CFN_ROLE_ARN, AWS_CLI_EXTRA_ARGS
EOF
  exit 2
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

stack_exists() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    "${AWS_CLI_EXTRA_ARGS[@]}" \
    >/dev/null 2>&1
}

read_kv_properties_to_args() {
  # Converts key=value lines into an array of args:
  # For tags: Key=...,Value=...
  # For parameters: ParameterKey=...,ParameterValue=...
  local file="$1"
  local kind="$2" # "tags" or "params"
  [[ -f "$file" ]] || return 0

  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue

    key="${line%%=*}"
    value="${line#*=}"

    # trim whitespace
    key="$(echo "$key" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    value="$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

    [[ -z "$key" ]] && continue

    if [[ "$kind" == "tags" ]]; then
      echo "Key=${key},Value=${value}"
    else
      echo "ParameterKey=${key},ParameterValue=${value}"
    fi
  done < "$file"
}

# ---- Validation --------------------------------------------------------------
[[ -n "$ENVIRONMENT" && -n "$MODE" ]] || usage
[[ "$MODE" == "create" || "$MODE" == "update" ]] || usage

require_cmd aws
[[ -f "$TEMPLATE_FILE" ]] || die "Template file not found: $TEMPLATE_FILE"

echo "Deploying stack: ${STACK_NAME}"
echo "Environment:     ${ENVIRONMENT}"
echo "Mode:            ${MODE}"
echo "Region:          ${AWS_REGION}"
echo "Template:        ${TEMPLATE_FILE}"
echo

# ---- Prepare Parameters ------------------------------------------------------
PARAM_ARGS=()

if [[ -f "$PARAMS_JSON_FILE" ]]; then
  # JSON format for Parameters: [{ "ParameterKey": "...", "ParameterValue": "..." }, ...]
  PARAM_ARGS+=(--parameters "file://${PARAMS_JSON_FILE}")
elif [[ -f "$PARAMS_PROPS_FILE" ]]; then
  # properties format: key=value per line
  mapfile -t PARAM_KV < <(read_kv_properties_to_args "$PARAMS_PROPS_FILE" "params")
  if (( ${#PARAM_KV[@]} > 0 )); then
    PARAM_ARGS+=(--parameters "${PARAM_KV[@]}")
  fi
else
  echo "No parameter file found for env '${ENVIRONMENT}'. Continuing with template defaults."
  echo "Checked: ${PARAMS_JSON_FILE} and ${PARAMS_PROPS_FILE}"
  echo
fi

# ---- Prepare Tags (optional) -------------------------------------------------
TAG_ARGS=()
if [[ -f "$TAGS_FILE" ]]; then
  mapfile -t TAG_KV < <(read_kv_properties_to_args "$TAGS_FILE" "tags")
  if (( ${#TAG_KV[@]} > 0 )); then
    TAG_ARGS+=(--tags "${TAG_KV[@]}")
  fi
fi

# ---- Role args (optional) ----------------------------------------------------
ROLE_ARGS=()
if [[ -n "$CFN_ROLE_ARN" ]]; then
  ROLE_ARGS+=(--role-arn "$CFN_ROLE_ARN")
fi

# ---- Existence checks --------------------------------------------------------
if [[ "$MODE" == "create" ]]; then
  if stack_exists; then
    die "Stack already exists: ${STACK_NAME}. Use 'update' mode instead."
  fi
else
  if ! stack_exists; then
    die "Stack does not exist: ${STACK_NAME}. Use 'create' mode instead."
  fi
fi

# ---- Prefer change sets for transparency ------------------------------------
CHANGE_SET_NAME="${STACK_NAME}-cs-$(date +%Y%m%d%H%M%S)"

# create-change-set supports both create + update (ChangeSetType differs)
CHANGE_SET_TYPE="UPDATE"
[[ "$MODE" == "create" ]] && CHANGE_SET_TYPE="CREATE"

echo "Creating change set: ${CHANGE_SET_NAME} (${CHANGE_SET_TYPE})"

aws cloudformation create-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --change-set-type "$CHANGE_SET_TYPE" \
  --template-body "file://${TEMPLATE_FILE}" \
  --capabilities "${CAPABILITIES[@]}" \
  "${PARAM_ARGS[@]}" \
  "${TAG_ARGS[@]}" \
  "${ROLE_ARGS[@]}" \
  --region "$AWS_REGION" \
  "${AWS_CLI_EXTRA_ARGS[@]}" \
  >/dev/null

# Wait for change set creation; handle "no changes" cleanly
set +e
aws cloudformation wait change-set-create-complete \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --region "$AWS_REGION" \
  "${AWS_CLI_EXTRA_ARGS[@]}"
WAIT_RC=$?
set -e

if [[ $WAIT_RC -ne 0 ]]; then
  STATUS_REASON="$(aws cloudformation describe-change-set \
    --stack-name "$STACK_NAME" \
    --change-set-name "$CHANGE_SET_NAME" \
    --region "$AWS_REGION" \
    "${AWS_CLI_EXTRA_ARGS[@]}" \
    --query 'StatusReason' --output text 2>/dev/null || true)"

  if echo "$STATUS_REASON" | grep -qi "didn't contain changes"; then
    echo "No changes to apply for stack ${STACK_NAME}."
    echo "Deleting empty change set ${CHANGE_SET_NAME}."
    aws cloudformation delete-change-set \
      --stack-name "$STACK_NAME" \
      --change-set-name "$CHANGE_SET_NAME" \
      --region "$AWS_REGION" \
      "${AWS_CLI_EXTRA_ARGS[@]}" \
      >/dev/null
    exit 0
  fi

  die "Change set failed: ${STATUS_REASON:-Unknown reason}"
fi

echo
echo "Change set details:"
aws cloudformation describe-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --region "$AWS_REGION" \
  "${AWS_CLI_EXTRA_ARGS[@]}" \
  --query 'Changes[].ResourceChange.{Action:Action,LogicalResourceId:LogicalResourceId,ResourceType:ResourceType,Replacement:Replacement}' \
  --output table

# Optional safety gate for prod
if [[ "$ENVIRONMENT" == "prod" ]]; then
  echo
  read -r -p "Type 'deploy' to execute change set in prod: " CONFIRM
  [[ "$CONFIRM" == "deploy" ]] || die "Aborted."
fi

echo
echo "Executing change set..."
aws cloudformation execute-change-set \
  --stack-name "$STACK_NAME" \
  --change-set-name "$CHANGE_SET_NAME" \
  --region "$AWS_REGION" \
  "${AWS_CLI_EXTRA_ARGS[@]}" \
  >/dev/null

echo "Waiting for stack operation to complete..."
if [[ "$MODE" == "create" ]]; then
  aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    "${AWS_CLI_EXTRA_ARGS[@]}"
else
  aws cloudformation wait stack-update-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    "${AWS_CLI_EXTRA_ARGS[@]}"
fi

echo
echo "Success. Current stack status:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  "${AWS_CLI_EXTRA_ARGS[@]}" \
  --query 'Stacks[0].{StackName:StackName,StackStatus:StackStatus,LastUpdatedTime:LastUpdatedTime,CreationTime:CreationTime}' \
  --output table
