# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS Cognito M2M (Machine-to-Machine) Token Caching Service with multi-region failover. Acts as an auth broker that presents a single `client_id/secret` to external M2M callers while internally managing multiple Cognito user pools across AWS regions. Uses the "pass-through Cognito tokens" pattern (Option 4.1 in `initial-version/DR.txt`) — the broker does not sign its own JWTs, it returns Cognito-issued tokens directly.

## Tech Stack

- **Runtime:** .NET 8 (dotnet8) on AWS Lambda
- **API:** ASP.NET Core hosted in Lambda behind API Gateway (SAM `AWS::Serverless::Function` with proxy integration)
- **IaC:** SAM/CloudFormation (`cognito-m2m-stack.yaml`)
- **Handler (Client App API):** `Ats.Cognito.ClientApp.Api`
- **Handler (Token Enrichment):** `AccessTokenEnrichmentDotnet::AccessTokenEnrichmentDotnet.Function::FunctionHandler`

## Deployment

```bash
# Deploy via CloudFormation change sets (requires AWS CLI configured)
./deploy-cfn.sh <environment> <create|update>
./deploy-cfn.sh sand create
./deploy-cfn.sh sand update
```

Stack name follows `${STACK_PREFIX}-${environment}` pattern (default prefix: `acsauth`). Default region: `ca-central-1`. Template uses SAM transform (`AWS::Serverless-2016-10-31`).

Parameters: `Application`, `Environment`, `CognitoDomainPrefix`, `ResourceServerId`

Parameter files live in `params/<environment>.properties`. Each environment gets a full independent stack — there is no shared test/prod resource server; each environment defines its own.

## Architecture

**Request flow:**
1. External client sends `client_id`, `client_secret`, `audience` to API Gateway
2. API Gateway proxies all requests to the ASP.NET Core Lambda (`/{proxy+}` with AWS_IAM auth, root `/` open)
3. Lambda checks DynamoDB `AccessTokenCache` for cached token (`PK=client_id|audience`, `SK=cache`)
4. Cache miss → Lambda creates a Cognito app client dynamically, calls Cognito `/oauth2/token` with Basic Auth
5. Token stored in cache with TTL at 95% of remaining token lifetime
6. Cognito `PreTokenGeneration` trigger invokes the enrichment Lambda, which reads client metadata from `ClientApps` table

**The Lambda manages Cognito app clients at runtime** (has `CreateUserPoolClient`/`DeleteUserPoolClient` permissions). App clients and table data are not defined in CloudFormation.

**Resources in the stack:**
- **DynamoDB:** `AccessTokenCache` (PK/SK, TTL on `ttl`), `ClientApps` (client_id/cognito_region)
- **Cognito:** User Pool with domain, resource server with `generate_token` scope
- **Lambda:** Client App API (SAM serverless function), Access Token Enrichment (pre-token generation trigger)
- **API Gateway:** Regional, SAM-managed, proxy to ASP.NET Core Lambda
- **IAM:** Deployment user (`${Application}-${Environment}-DeploymentUser`) for Azure DevOps CI/CD, scoped to the stack's Lambda functions

**Naming convention:** All resources use `${Application}-${Environment}-` prefix (e.g. `acsauth-sand-AccessTokenCache`).

## Key Files

- `cognito-m2m-stack.yaml` — SAM/CloudFormation template (primary IaC)
- `deploy-cfn.sh` — Deployment script using change sets with prod safety gate
- `params/sand.properties` — Sandbox environment parameters
- `params/dev.properties` — Dev environment parameters
- `initial-version/DR.txt` — Design rationale (pass-through vs broker-issued tokens)
- `initial-version/` — Legacy Python reference implementation (no longer active)
