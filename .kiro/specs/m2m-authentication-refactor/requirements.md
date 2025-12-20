# Requirements Document

## Introduction

Healthmate-CoachAI サービスを、現在のJWTトークンベースの認証からM2M（Machine-to-Machine）認証を使用してHealthManager MCPサービスにアクセスするようにリファクタリングします。これにより、より安全で標準的なサービス間認証を実現します。

## Glossary

- **M2M Authentication**: Machine-to-Machine認証。サービス間の自動認証方式
- **AgentCore Identity**: Amazon Bedrock AgentCoreのWorkload Identity機能
- **@requires_access_token**: AgentCore Runtimeが提供するM2M認証デコレータ
- **Provider Name**: AgentCore Identityで設定される認証プロバイダー名
- **Cognito Scope**: Cognito OAuth2で定義されるアクセススコープ
- **BEDROCK_AGENTCORE_MEMORY_ID**: AgentCore Runtimeで設定されるメモリーID環境変数
- **Healthmate-CoachAI**: AI健康コーチエージェントサービス
- **HealthManager MCP**: 健康データ管理MCPサーバーサービス

## Requirements

### Requirement 1

**User Story:** As a system architect, I want to implement M2M authentication for service-to-service communication, so that the system follows security best practices and reduces dependency on user JWT tokens.

#### Acceptance Criteria

1. WHEN the CoachAI agent needs to access HealthManager MCP THEN the system SHALL use @requires_access_token decorator for M2M authentication
2. WHEN M2M authentication is configured THEN the system SHALL use provider_name from environment variables
3. WHEN M2M authentication is configured THEN the system SHALL use cognito_scope "HealthManager/HealthTarget:invoke"
4. WHEN M2M authentication is configured THEN the system SHALL use auth_flow "M2M"
5. WHEN M2M authentication is configured THEN the system SHALL set force_authentication to False

### Requirement 2

**User Story:** As a developer, I want the agent.py to use the @requires_access_token decorator, so that MCP client creation is properly authenticated.

#### Acceptance Criteria

1. WHEN creating MCP client THEN the system SHALL apply @requires_access_token decorator to get_mcp_client_from_gateway function
2. WHEN @requires_access_token decorator is applied THEN the access_token SHALL be passed as function argument
3. WHEN MCP client is created THEN the system SHALL use the provided access_token for authentication
4. WHEN MCP Gateway is called THEN the system SHALL use Bearer token authentication with the access_token
5. WHEN MCP client creation fails THEN the system SHALL provide clear error messages

### Requirement 3

**User Story:** As a deployment engineer, I want the deploy_to_aws.sh script to set the provider_name environment variable, so that M2M authentication is properly configured.

#### Acceptance Criteria

1. WHEN deploying the agent THEN the system SHALL set AGENTCORE_PROVIDER_NAME environment variable
2. WHEN AGENTCORE_PROVIDER_NAME is set THEN the value SHALL be "healthmanager-oauth2-provider"
3. WHEN environment variables are configured THEN the system SHALL maintain existing HEALTHMANAGER_GATEWAY_ID and AWS_REGION variables
4. WHEN deployment script runs THEN the system SHALL verify that required CloudFormation outputs exist
5. WHEN deployment completes THEN the system SHALL provide clear success confirmation

### Requirement 4

**User Story:** As a system administrator, I want strict memory ID validation, so that the system fails fast when required configuration is missing.

#### Acceptance Criteria

1. WHEN BEDROCK_AGENTCORE_MEMORY_ID environment variable is not set THEN the system SHALL raise an error immediately
2. WHEN memory ID is missing THEN the system SHALL NOT attempt fallback API calls to retrieve memory
3. WHEN memory ID validation fails THEN the system SHALL provide clear error message indicating configuration issue
4. WHEN memory ID is properly set THEN the system SHALL use it for AgentCore Memory configuration
5. WHEN memory configuration fails THEN the system SHALL stop processing and report the error

### Requirement 5

**User Story:** As a developer, I want to remove JWT token processing logic, so that the system uses M2M authentication exclusively.

#### Acceptance Criteria

1. WHEN M2M authentication is implemented THEN the system SHALL remove JWT token extraction from payload
2. WHEN M2M authentication is implemented THEN the system SHALL remove _get_jwt_token function
3. WHEN M2M authentication is implemented THEN the system SHALL remove _decode_jwt_payload function
4. WHEN M2M authentication is implemented THEN the system SHALL remove _get_sub_from_jwt function
5. WHEN user identification is needed THEN the system SHALL use alternative methods compatible with M2M authentication

### Requirement 6

**User Story:** As a security engineer, I want the system to use AgentCore Identity for authentication, so that credentials are managed securely by AWS services.

#### Acceptance Criteria

1. WHEN AgentCore Identity is used THEN the system SHALL leverage Healthmate-HealthManager's Workload Identity configuration
2. WHEN credentials are needed THEN the system SHALL use OAuth2 Credential Provider created by HealthManager service
3. WHEN authentication occurs THEN the system SHALL use Client Credentials flow for M2M authentication
4. WHEN access tokens are obtained THEN the system SHALL use them for MCP Gateway authentication
5. WHEN authentication fails THEN the system SHALL provide appropriate error handling and logging