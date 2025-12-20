# Design Document

## Overview

This design document outlines the refactoring of Healthmate-CoachAI service to use M2M (Machine-to-Machine) authentication instead of JWT token-based authentication for accessing HealthManager MCP services. The refactoring will implement AgentCore Identity with OAuth2 Credential Provider for secure service-to-service communication.

## Architecture

### Current Architecture
```
HealthmateUI → JWT Token → CoachAI Agent → JWT-based MCP calls → HealthManager MCP
```

### New Architecture
```
HealthmateUI → Session Data → CoachAI Agent → M2M Auth → HealthManager MCP
                                    ↓
                            AgentCore Identity
                                    ↓
                            OAuth2 Credential Provider
                                    ↓
                            Cognito Client Credentials Flow
```

### Key Changes
1. **Authentication Method**: Replace JWT token extraction with @requires_access_token decorator
2. **Credential Management**: Use AgentCore Identity and OAuth2 Credential Provider
3. **Environment Configuration**: Add AGENTCORE_PROVIDER_NAME environment variable
4. **Memory Validation**: Enforce strict BEDROCK_AGENTCORE_MEMORY_ID validation
5. **Code Cleanup**: Remove JWT processing functions

## Components and Interfaces

### Modified Components

#### 1. agent.py
- **get_mcp_client_from_gateway()**: New function with @requires_access_token decorator
- **MCP Gateway calls**: Updated to use M2M access tokens
- **Memory configuration**: Strict validation of BEDROCK_AGENTCORE_MEMORY_ID
- **Removed functions**: JWT processing functions (_get_jwt_token, _decode_jwt_payload, etc.)

#### 2. deploy_to_aws.sh
- **Environment variables**: Add AGENTCORE_PROVIDER_NAME configuration
- **Validation**: Verify CloudFormation outputs for M2M setup
- **AgentCore launch**: Include new environment variable in deployment

### Integration Points

#### AgentCore Identity Integration
```python
@requires_access_token(
    provider_name=provider_name,
    scopes=[cognito_scope],
    auth_flow="M2M",
    force_authentication=False,
)
def get_mcp_client_from_gateway(access_token: str):
    # Access token is provided as function argument
    # Use token for MCP Gateway authentication
```

#### Environment Configuration
```bash
# Required environment variables
AGENTCORE_PROVIDER_NAME="healthmanager-oauth2-provider"
HEALTHMANAGER_GATEWAY_ID="<gateway-id>"
AWS_REGION="us-west-2"
BEDROCK_AGENTCORE_MEMORY_ID="<memory-id>"
```

## Data Models

### Authentication Configuration
```python
class M2MAuthConfig:
    provider_name: str = "healthmanager-oauth2-provider"
    cognito_scope: str = "HealthManager/HealthTarget:invoke"
    auth_flow: str = "M2M"
    force_authentication: bool = False
```

### MCP Client Configuration
```python
class MCPClientConfig:
    gateway_endpoint: str
    access_token: str
    timeout: float = 30.0
```

### Memory Configuration
```python
class MemoryConfig:
    memory_id: str  # Required from BEDROCK_AGENTCORE_MEMORY_ID
    session_id: str  # From payload
    actor_id: str   # From alternative identification method
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After reviewing all properties identified in the prework, the following consolidations were made:
- Properties 1.2, 3.1, 3.2 can be combined into a single environment configuration property
- Properties 2.2, 2.3, 2.4 can be combined into a comprehensive access token usage property
- Properties 5.1, 5.2, 5.3, 5.4 can be combined into a single JWT removal property
- Properties 4.1, 4.3 can be combined into a single memory validation property

### Core Properties

**Property 1: M2M Authentication Decorator Usage**
*For any* MCP client creation request, the get_mcp_client_from_gateway function should be decorated with @requires_access_token and use correct M2M authentication parameters
**Validates: Requirements 1.1, 1.3, 1.4, 1.5, 2.1**

**Property 2: Access Token Integration**
*For any* MCP Gateway call, the system should use the access_token parameter provided by the decorator for Bearer token authentication
**Validates: Requirements 2.2, 2.3, 2.4**

**Property 3: Environment Configuration**
*For any* deployment, the system should set AGENTCORE_PROVIDER_NAME to "healthmanager-oauth2-provider" and maintain existing environment variables
**Validates: Requirements 1.2, 3.1, 3.2, 3.3**

**Property 4: Memory ID Validation**
*For any* agent initialization, when BEDROCK_AGENTCORE_MEMORY_ID is not set, the system should raise an error immediately without attempting fallback operations
**Validates: Requirements 4.1, 4.2, 4.3**

**Property 5: JWT Function Removal**
*For any* code inspection, the system should not contain JWT processing functions (_get_jwt_token, _decode_jwt_payload, _get_sub_from_jwt)
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

**Property 6: AgentCore Identity Integration**
*For any* authentication request, the system should use the OAuth2 Credential Provider and Client Credentials flow configured in HealthManager service
**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

**Property 7: Error Handling**
*For any* authentication or MCP client creation failure, the system should provide clear error messages and appropriate error handling
**Validates: Requirements 2.5, 4.5, 6.5**

## Error Handling

### Authentication Errors
- **Missing Provider Name**: Clear error when AGENTCORE_PROVIDER_NAME is not set
- **Invalid Credentials**: Proper error handling for OAuth2 authentication failures
- **Token Expiration**: Automatic token refresh through AgentCore Identity

### Configuration Errors
- **Missing Memory ID**: Immediate error when BEDROCK_AGENTCORE_MEMORY_ID is not set
- **Invalid Gateway ID**: Clear error when HealthManager Gateway is not accessible
- **Missing CloudFormation Outputs**: Validation errors during deployment

### MCP Communication Errors
- **Gateway Unavailable**: Timeout and retry logic for MCP Gateway calls
- **Invalid Responses**: Proper parsing and error handling for MCP responses
- **Network Issues**: Appropriate error messages for connectivity problems

## Testing Strategy

### Unit Testing
- Test @requires_access_token decorator application
- Test environment variable configuration
- Test error handling for missing configuration
- Test MCP client creation with valid access tokens
- Test memory configuration validation

### Integration Testing
- Test M2M authentication flow end-to-end
- Test MCP Gateway communication with real credentials
- Test AgentCore Identity integration
- Test deployment script with CloudFormation validation

### Property-Based Testing
Using pytest with hypothesis for comprehensive testing:
- Generate random configuration scenarios
- Test authentication with various token formats
- Test error conditions with invalid configurations
- Test MCP communication with different response types

### Testing Framework
- **Framework**: pytest with hypothesis (property-based testing)
- **Mocking**: moto for AWS services, unittest.mock for AgentCore components
- **Coverage**: pytest-cov for code coverage analysis
- **Configuration**: pytest.ini with verbose output and short tracebacks