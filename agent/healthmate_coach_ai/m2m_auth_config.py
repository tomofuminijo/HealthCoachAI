"""
M2M認証設定モジュール

AgentCore IdentityとOAuth2 Credential Providerを使用した
Machine-to-Machine認証の設定を管理します。
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class M2MAuthConfig:
    """M2M認証設定クラス"""
    provider_name: str
    cognito_scope: str
    auth_flow: str
    force_authentication: bool
    
    @classmethod
    def from_environment(cls) -> 'M2MAuthConfig':
        """環境変数からM2M認証設定を作成"""
        provider_name = os.environ.get('AGENTCORE_PROVIDER_NAME')
        if not provider_name:
            raise ValueError(
                "環境変数 AGENTCORE_PROVIDER_NAME が設定されていません。"
                "M2M認証には必須の設定です。"
            )
        
        return cls(
            provider_name=provider_name,
            cognito_scope="HealthManager/HealthTarget:invoke",
            auth_flow="M2M",
            force_authentication=False
        )


def get_m2m_auth_config() -> M2MAuthConfig:
    """M2M認証設定を取得"""
    return M2MAuthConfig.from_environment()


def validate_environment_variables() -> None:
    """M2M認証に必要な環境変数を検証"""
    required_vars = [
        'AGENTCORE_PROVIDER_NAME',
        'HEALTHMANAGER_GATEWAY_ID',
        'AWS_REGION',
        'BEDROCK_AGENTCORE_MEMORY_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(
            f"以下の必須環境変数が設定されていません: {', '.join(missing_vars)}"
        )


def get_gateway_endpoint() -> str:
    """MCP Gateway エンドポイントを環境変数から取得"""
    gateway_id = os.environ.get('HEALTHMANAGER_GATEWAY_ID')
    if not gateway_id:
        raise ValueError("環境変数 HEALTHMANAGER_GATEWAY_ID が設定されていません")
    
    region = os.environ.get('AWS_REGION', 'us-west-2')
    return f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"


def get_memory_id() -> str:
    """AgentCore Memory IDを環境変数から取得（厳格な検証）"""
    memory_id = os.environ.get('BEDROCK_AGENTCORE_MEMORY_ID')
    if not memory_id:
        raise ValueError(
            "環境変数 BEDROCK_AGENTCORE_MEMORY_ID が設定されていません。"
            "AgentCore Memory統合には必須の設定です。"
            "フォールバック処理は行いません。"
        )
    
    return memory_id