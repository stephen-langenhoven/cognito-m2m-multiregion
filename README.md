# Cognito M2M Multi-Region

AWS Cognito Machine-to-Machine (M2M) Token Caching Service with multi-region failover. Acts as an auth broker presenting a single `client_id/secret` to external M2M callers while internally managing multiple Cognito user pools across AWS regions. Uses the pass-through Cognito tokens pattern — the broker returns Cognito-issued JWTs directly.

## Architecture

- **API Gateway** (regional) proxies all requests to an ASP.NET Core Lambda
- **Client App API Lambda** (.NET 8) handles token caching, Cognito client management, and DynamoDB operations
- **Access Token Enrichment Lambda** (.NET 8) runs as a Cognito `PreTokenGeneration` trigger, reading client metadata from DynamoDB
- **Cognito User Pool** with a resource server and `generate_token` scope; app clients are created at runtime by the API Lambda
- **DynamoDB** tables for token caching (`AccessTokenCache`) and client configuration (`ClientApps`)
- **IAM Deployment User** for Azure DevOps CI/CD pipeline, scoped to the stack's Lambda functions

## Prerequisites

- AWS CLI configured with appropriate credentials
- Target AWS region defaults to `ca-central-1` (override with `AWS_REGION`)

## Deployment

### 1. Bootstrap the deployment artifacts bucket (once per environment)

Creates an S3 bucket and uploads a placeholder zip required for initial Lambda creation. Dotnet8 Lambdas cannot use inline code, so both functions reference this placeholder until CI/CD deploys the real code.

```bash
./bootstrap-artifacts.sh <environment>

# Example:
./bootstrap-artifacts.sh dev
```

### 2. Deploy the CloudFormation stack

```bash
./deploy-cfn.sh <environment> <create|update>

# Examples:
./deploy-cfn.sh dev create    # First-time deployment
./deploy-cfn.sh dev update    # Subsequent updates
```

The stack name follows the pattern `${STACK_PREFIX}-${environment}` (default prefix: `acsauth`).

Production deployments require interactive confirmation before executing the change set.

### 3. CI/CD deploys Lambda code

The Azure DevOps pipeline uses the `${Application}-${Environment}-DeploymentUser` IAM user (created by the stack) to push compiled .NET 8 code to both Lambda functions via `UpdateFunctionCode`.

## Parameters

Defined in `params/<environment>.properties`:

| Parameter | Description | Example |
|---|---|---|
| `Application` | Application name prefix | `acsauth` |
| `Environment` | Environment name | `dev`, `sand`, `prod` |
| `CognitoDomainPrefix` | Cognito hosted UI domain (globally unique) | `m2m-token-dev` |
| `ResourceServerId` | Resource server identifier | `https://test.api.ats.healthcare` |

Each environment gets a fully independent stack — there are no shared resources between environments.

## Naming Convention

All resources use `${Application}-${Environment}-` prefix:
- `acsauth-dev-AccessTokenCache`
- `acsauth-dev-ClientApps`
- `acsauth-dev-ClientAppApi`
- `acsauth-dev-AccessTokenEnrichment`
- `acsauth-dev-DeploymentUser`
- etc.

## Key Files

| File | Purpose |
|---|---|
| `cognito-m2m-stack.yaml` | CloudFormation template |
| `deploy-cfn.sh` | Stack deployment script (change set based) |
| `bootstrap-artifacts.sh` | One-time S3 bucket and placeholder setup |
| `params/*.properties` | Per-environment parameters |
| `initial-version/DR.txt` | Design rationale document |
