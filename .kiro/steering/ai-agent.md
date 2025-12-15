# HealthCoachAI サービス

## Service Overview

HealthCoachAI サービスは、Healthmate プロダクトのAI健康コーチを担当するエージェントです。Amazon Bedrock AgentCore Runtime上で動作し、ユーザーにパーソナライズされた健康アドバイスを提供します。

### Primary Responsibilities

- **AI Health Coaching**: ユーザーの健康データに基づくパーソナライズされたアドバイス
- **MCP Client**: HealthManagerMCP サービスからの健康データ取得
- **JWT Processing**: フロントエンドから渡されるJWTトークンの処理とユーザー識別
- **Time-Aware Responses**: 現在時刻を考慮した適切なタイミングでのアドバイス

### Service Architecture

- **Framework**: Strands Agent SDK
- **Runtime**: Amazon Bedrock AgentCore Runtime
- **Platform**: Linux/ARM64 containers
- **Deployment**: Container-based deployment with ECR
- **Configuration**: CloudFormation outputs for dynamic configuration

### Key Technologies

#### Core Dependencies
- **strands-agents**: Agent framework for tool integration
- **bedrock-agentcore**: Runtime environment integration
- **mcp**: Model Context Protocol client
- **boto3**: AWS SDK for CloudFormation and Cognito integration
- **pytz**: Timezone handling for time-aware responses

#### Development Tools
- **pytest**: Unit and integration testing
- **black**: Code formatting
- **mypy**: Type checking

### Agent Patterns

#### JWT Token Handling
```python
def _decode_jwt_payload(jwt_token: str) -> dict:
    """JWTトークンのペイロードをデコード（署名検証なし）"""
    # Base64URL decoding with padding adjustment
```

#### MCP Integration
```python
async def _call_mcp_tool(tool_name: str, parameters: dict) -> dict:
    """HealthManagerMCP サービスのツールを呼び出し"""
    # HTTP client with proper authentication headers
```

#### Time-Aware Responses
```python
def _get_current_time_in_timezone(timezone_str: str = "Asia/Tokyo") -> datetime:
    """ユーザーのタイムゾーンでの現在時刻を取得"""
```

### Configuration Management

#### Environment Variables
- `HEALTHMANAGER_GATEWAY_ID`: MCP Gateway endpoint
- `AWS_REGION`: AWS region (default: us-west-2)
- `HEALTH_STACK_NAME`: CloudFormation stack name for dynamic config

#### CloudFormation Integration
```python
def _get_config_from_cloudformation() -> dict:
    """CloudFormationスタックから設定を動的取得"""
    # Gateway ID, Cognito settings from stack outputs
```

### Deployment Patterns

#### One-Command Deployment
```bash
./deploy_to_aws.sh  # IAM role creation + AgentCore deployment
```

#### Custom IAM Role
- **Role Name**: `HealthCoachAI-AgentCore-Runtime-Role`
- **Permissions**: AgentCore Runtime + CloudFormation read + Cognito read

#### Testing Strategy
- **Interactive Testing**: `manual_test_agent.py` for development
- **Deployed Testing**: `manual_test_deployed_agent.py` for production validation
- **Status Monitoring**: `check_deployment_status.py` for deployment verification

### Integration Points

- **HealthManagerMCP サービス**: MCP protocol for health data access
- **HealthmateUI サービス**: JWT token passing for user identification
- **External AI Platforms**: Potential integration with other AI services

### Service-Specific Best Practices

- **Error Handling**: Graceful fallback when MCP services are unavailable
- **User Context**: Always extract user ID from JWT for personalized responses
- **Time Sensitivity**: Consider user's timezone and current time for advice
- **Security**: Never log or expose JWT tokens or sensitive user data