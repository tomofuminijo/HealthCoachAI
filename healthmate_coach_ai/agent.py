"""
Healthmate-CoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する
健康支援AIエージェントです。
"""

import os
import asyncio
import httpx
import json
import base64
from datetime import datetime
from typing import Optional
import pytz
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

# M2M認証用デコレータのインポート
try:
    from bedrock_agentcore.identity.auth import requires_access_token
    print("DEBUG: Successfully imported requires_access_token from bedrock_agentcore.identity.auth")
except ImportError:
    try:
        from bedrock_agentcore.runtime import requires_access_token
        print("DEBUG: Successfully imported requires_access_token from bedrock_agentcore.runtime")
    except ImportError:
        try:
            from bedrock_agentcore import requires_access_token
            print("DEBUG: Successfully imported requires_access_token from bedrock_agentcore")
        except ImportError:
            print("WARNING: Could not import requires_access_token decorator")
            # フォールバック: デコレータなしで動作するようにダミーを定義
            def requires_access_token(**kwargs):
                def decorator(func):
                    return func
                return decorator
            print("DEBUG: Using fallback requires_access_token decorator")


# M2M認証設定クラス
class M2MAuthConfig:
    """M2M認証設定を管理するクラス"""
    
    def __init__(self):
        self.provider_name = self._get_provider_name()
        self.cognito_scope = "HealthManager/HealthTarget:invoke"
        self.auth_flow = "M2M"
        self.force_authentication = False
    
    def _get_provider_name(self) -> str:
        """AGENTCORE_PROVIDER_NAME環境変数を取得"""
        provider_name = os.environ.get('AGENTCORE_PROVIDER_NAME')
        if not provider_name:
            raise Exception("環境変数 AGENTCORE_PROVIDER_NAME が設定されていません。M2M認証には必須です。")
        
        print(f"DEBUG: M2M Provider Name: {provider_name}")
        return provider_name
    
    def get_scopes(self) -> list:
        """認証スコープのリストを取得"""
        return [self.cognito_scope]
    
    def validate_config(self) -> bool:
        """設定の妥当性を検証"""
        if not self.provider_name:
            return False
        if not self.cognito_scope:
            return False
        if self.auth_flow != "M2M":
            return False
        return True


# 環境変数設定管理
def _get_gateway_endpoint() -> str:
    """Gateway エンドポイントを環境変数から取得"""
    gateway_id = os.environ.get('HEALTHMANAGER_GATEWAY_ID')
    if not gateway_id:
        raise Exception("環境変数 HEALTHMANAGER_GATEWAY_ID が設定されていません")
    
    region = os.environ.get('AWS_REGION', 'us-west-2')
    return f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"


def _get_memory_id() -> str:
    """BEDROCK_AGENTCORE_MEMORY_ID環境変数を厳格に検証して取得"""
    memory_id = os.environ.get('BEDROCK_AGENTCORE_MEMORY_ID')
    
    if not memory_id:
        error_msg = (
            "環境変数 BEDROCK_AGENTCORE_MEMORY_ID が設定されていません。\n"
            "AgentCore Memory機能には必須です。\n"
            "システム管理者に連絡してください。\n"
            "設定方法: export BEDROCK_AGENTCORE_MEMORY_ID=<your-memory-id>"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    
    # メモリIDの形式を簡単に検証
    if len(memory_id.strip()) == 0:
        error_msg = (
            "環境変数 BEDROCK_AGENTCORE_MEMORY_ID が空です。\n"
            "有効なメモリIDを設定してください。"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    
    # メモリIDの長さを検証（一般的なAWSリソースIDの最小長）
    if len(memory_id) < 10:
        error_msg = (
            f"環境変数 BEDROCK_AGENTCORE_MEMORY_ID の値が短すぎます（{len(memory_id)}文字）。\n"
            "有効なメモリIDを設定してください。"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    
    print(f"DEBUG: Memory ID validated successfully: {memory_id}")
    return memory_id


def _validate_memory_config(memory_id: str, session_id: str, actor_id: str) -> bool:
    """AgentCore Memory設定パラメータの妥当性を検証"""
    errors = []
    
    # メモリIDの検証
    if not memory_id or len(memory_id.strip()) == 0:
        errors.append("Memory ID が空です")
    elif len(memory_id) < 10:
        errors.append(f"Memory ID が短すぎます（{len(memory_id)}文字）")
    
    # セッションIDの検証
    if not session_id or len(session_id.strip()) == 0:
        errors.append("Session ID が空です")
    elif len(session_id) < 33:
        errors.append(f"Session ID が短すぎます（{len(session_id)}文字、33文字以上が必要）")
    
    # アクターIDの検証
    if not actor_id or len(actor_id.strip()) == 0:
        errors.append("Actor ID が空です")
    
    if errors:
        error_msg = "AgentCore Memory設定パラメータエラー:\n" + "\n".join(f"  - {error}" for error in errors)
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    
    print(f"DEBUG: Memory config parameters validated successfully")
    return True


def _validate_required_environment_variables():
    """必須環境変数の存在を事前に検証"""
    required_vars = {
        'AGENTCORE_PROVIDER_NAME': 'M2M認証プロバイダー名',
        'HEALTHMANAGER_GATEWAY_ID': 'HealthManager MCPゲートウェイID'
    }
    
    missing_vars = []
    
    for var_name, description in required_vars.items():
        value = os.environ.get(var_name)
        if not value or len(value.strip()) == 0:
            missing_vars.append(f"  - {var_name}: {description}")
    
    if missing_vars:
        error_msg = (
            "以下の必須環境変数が設定されていません:\n" +
            "\n".join(missing_vars) +
            "\n\nシステム管理者に連絡してください。"
        )
        print(f"ERROR: Environment validation failed")
        print(f"ERROR: {error_msg}")
        raise Exception(f"環境変数検証エラー: {error_msg}")
    
    print(f"DEBUG: All required environment variables are present")
    return True

# グローバル変数（JWT処理用とM2M認証設定用）
_current_jwt_token = None
_current_timezone = None
_current_language = None

# M2M認証設定のグローバルインスタンス
try:
    # 起動時に必須環境変数を検証
    _validate_required_environment_variables()
    
    _m2m_auth_config = M2MAuthConfig()
    print(f"DEBUG: M2M認証設定が正常に初期化されました")
    
    # M2M認証パラメータをグローバル変数として設定
    _M2M_PROVIDER_NAME = _m2m_auth_config.provider_name
    _M2M_SCOPES = _m2m_auth_config.get_scopes()
    
except Exception as e:
    print(f"ERROR: M2M認証設定の初期化に失敗しました: {e}")
    print(f"ERROR: アプリケーションは起動できません")
    _m2m_auth_config = None
    _M2M_PROVIDER_NAME = None
    _M2M_SCOPES = None
    # 環境変数が不足している場合は起動を中止
    raise


def _get_m2m_auth_config() -> M2MAuthConfig:
    """M2M認証設定を取得"""
    global _m2m_auth_config
    
    if _m2m_auth_config is None:
        try:
            _m2m_auth_config = M2MAuthConfig()
        except Exception as e:
            raise Exception(f"M2M認証設定の取得に失敗しました: {e}")
    
    if not _m2m_auth_config.validate_config():
        raise Exception("M2M認証設定が無効です。環境変数を確認してください。")
    
    return _m2m_auth_config


def _get_m2m_auth_config() -> M2MAuthConfig:
    """M2M認証設定を取得"""
    global _m2m_auth_config
    
    if _m2m_auth_config is None:
        try:
            _m2m_auth_config = M2MAuthConfig()
        except Exception as e:
            raise Exception(f"M2M認証設定の取得に失敗しました: {e}")
    
    if not _m2m_auth_config.validate_config():
        raise Exception("M2M認証設定が無効です。環境変数を確認してください。")
    
    return _m2m_auth_config


@requires_access_token(
    provider_name=_M2M_PROVIDER_NAME,
    scopes=_M2M_SCOPES,
    auth_flow="M2M",
    force_authentication=False,
)
def get_mcp_client_from_gateway(access_token: str):
    """
    M2M認証を使用してMCPクライアントを作成
    
    注意: @requires_access_tokenデコレータがaccess_tokenを自動提供
    私たちは自分でM2M認証を実装する必要はない
    
    Args:
        access_token: @requires_access_tokenデコレータから自動提供されるアクセストークン
    
    Returns:
        MCPクライアント設定情報
    """
    try:
        # M2M認証設定を取得
        auth_config = _get_m2m_auth_config()
        
        # Gateway エンドポイントを取得
        gateway_endpoint = _get_gateway_endpoint()
        
        print(f"DEBUG: Creating MCP client with M2M authentication")
        print(f"DEBUG: Provider: {auth_config.provider_name}")
        print(f"DEBUG: Scopes: {auth_config.get_scopes()}")
        print(f"DEBUG: Gateway: {gateway_endpoint}")
        print(f"DEBUG: Access token provided by @requires_access_token decorator")
        
        if not access_token:
            raise Exception("@requires_access_tokenデコレータからアクセストークンが提供されませんでした")
        
        # MCPクライアント設定を返す
        return {
            "gateway_endpoint": gateway_endpoint,
            "access_token": access_token,
            "auth_config": {
                "provider_name": auth_config.provider_name,
                "scopes": auth_config.get_scopes(),
                "auth_flow": auth_config.auth_flow
            }
        }
        
    except Exception as e:
        print(f"ERROR: MCP client creation failed: {e}")
        raise Exception(f"MCPクライアント作成エラー: {e}")


# JWT Token ヘルパー関数（ユーザー識別専用）
# 用途: HealthmateUIから渡されるユーザーJWTトークンからユーザーIDを抽出
# 注意: MCP Gateway認証には使用しない（M2M認証を使用）
def _decode_jwt_payload(jwt_token: str) -> dict:
    """
    JWTトークンのペイロードをデコード（署名検証なし）
    
    用途: HealthmateUIから渡されるユーザーJWTトークンからユーザー情報を取得
    注意: MCPゲートウェイ認証には使用しない（M2M認証を使用）
    
    Args:
        jwt_token: HealthmateUIから渡されるユーザーのJWTトークン
    
    Returns:
        JWTペイロードの辞書
    """
    try:
        # JWTは "header.payload.signature" の形式
        parts = jwt_token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # ペイロード部分をデコード
        payload = parts[1]
        
        # Base64URLデコードのためのパディング調整
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += '=' * padding
        
        # Base64デコードしてJSONパース
        decoded_bytes = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded_bytes.decode('utf-8'))
        
        return payload_data
        
    except Exception as e:
        print(f"JWT デコードエラー: {e}")
        return {}


def _get_jwt_token():
    """
    JWT認証トークンを取得（ユーザー識別用）
    
    用途: HealthmateUIから渡されるユーザーJWTトークンを取得
    注意: MCPゲートウェイ認証には使用しない（M2M認証を使用）
    
    Returns:
        ユーザーのJWTトークン文字列、または None
    """
    global _current_jwt_token
    
    try:
        # まずグローバル変数から取得を試行
        if _current_jwt_token:
            print(f"DEBUG: JWT token from global variable: {_current_jwt_token[:50]}...")
            return _current_jwt_token
        
        # AgentCore Runtime環境でUIから渡されたJWTトークンを取得
        try:
            jwt_token = BedrockAgentCoreContext.get_workload_access_token()
            if jwt_token:
                print(f"DEBUG: JWT token from get_workload_access_token: {jwt_token[:50]}...")
                return jwt_token
        except Exception as e:
            print(f"DEBUG: get_workload_access_token エラー: {e}")
        
        # フォールバック: リクエストヘッダーからAuthorizationを取得
        try:
            headers = BedrockAgentCoreContext.get_request_headers()
            print(f"DEBUG: Request headers: {headers}")
            
            if headers and 'Authorization' in headers:
                auth_header = headers['Authorization']
                if auth_header.startswith('Bearer '):
                    jwt_token = auth_header[7:]  # "Bearer " を除去
                    print(f"DEBUG: JWT token from Authorization header: {jwt_token[:50]}...")
                    return jwt_token
        except Exception as e:
            print(f"DEBUG: get_request_headers エラー: {e}")
        
        print(f"DEBUG: JWT token not found in any source")
        return None
        
    except Exception as e:
        print(f"DEBUG: JWT token取得エラー: {e}")
        return None


def _get_sub_from_jwt():
    """
    JWTトークンからsubを取得（ユーザー識別用）
    
    用途: HealthmateUIから渡されるユーザーJWTトークンからユーザーID（sub）を取得
    これはAgentCore MemoryのActor IDとして使用されます
    
    Returns:
        ユーザーID（sub）文字列、または None
    """
    try:
        jwt_token = _get_jwt_token()
        if not jwt_token:
            print(f"DEBUG: No JWT token available for user ID extraction")
            return None
        
        payload = _decode_jwt_payload(jwt_token)
        if not payload:
            print(f"DEBUG: Failed to decode JWT payload")
            return None
            
        sub = payload.get('sub') 
        
        if not sub:
            print(f"DEBUG: No 'sub' field found in JWT payload")
            # 例外を投げる
            raise ValueError("JWT payload missing 'sub' field")

        print(f"DEBUG: Extracted sub from JWT: {sub}")
        return sub
        
    except Exception as e:
        print(f"ERROR: sub 取得エラー: {e}")
        return None


def _get_user_timezone():
    """ペイロードから設定されたタイムゾーンを取得"""
    global _current_timezone
    
    if _current_timezone:
        print(f"DEBUG: Using timezone from payload: {_current_timezone}")
        return _current_timezone
    else:
        print(f"DEBUG: No timezone found in payload, using default: Asia/Tokyo")
        return 'Asia/Tokyo'


def _get_user_language():
    """ペイロードから設定された言語を取得"""
    global _current_language
    
    if _current_language:
        print(f"DEBUG: Using language from payload: {_current_language}")
        return _current_language
    else:
        print(f"DEBUG: No language found in payload, using default: ja")
        return 'ja'


def _get_language_name(language_code: str) -> str:
    """言語コードを言語名に変換"""
    language_map = {
        'ja': '日本語',
        'en': 'English',
        'en-us': 'English (US)',
        'en-gb': 'English (UK)',
        'zh': '中文',
        'zh-cn': '中文 (简体)',
        'zh-tw': '中文 (繁體)',
        'ko': '한국어',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'it': 'Italiano',
        'pt': 'Português',
        'ru': 'Русский'
    }
    return language_map.get(language_code.lower(), language_code)


def _get_localized_datetime(timezone_str: str = 'Asia/Tokyo'):
    """指定されたタイムゾーンでの現在日時を取得"""
    try:
        # タイムゾーンの有効性を確認
        try:
            user_timezone = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            print(f"DEBUG: Invalid timezone: {timezone_str}, using Asia/Tokyo")
            user_timezone = pytz.timezone('Asia/Tokyo')
        
        # UTC時刻を取得してユーザーのタイムゾーンに変換
        utc_now = datetime.now(pytz.UTC)
        local_datetime = utc_now.astimezone(user_timezone)
        
        return local_datetime
        
    except Exception as e:
        print(f"DEBUG: ローカル日時取得エラー: {e}")
        # エラー時はJSTで返す
        jst = pytz.timezone('Asia/Tokyo')
        utc_now = datetime.now(pytz.UTC)
        return utc_now.astimezone(jst)


async def _call_mcp_gateway_with_m2m(method: str, params: dict = None):
    """
    M2M認証を使用してMCP Gatewayを呼び出す関数
    
    用途: Agent → Gateway呼び出しの認証専用
    注意: @requires_access_tokenデコレータが自動的にM2M認証を処理
    
    Args:
        method: MCPメソッド名
        params: MCPパラメータ
    
    Returns:
        MCP呼び出し結果
    
    Raises:
        Exception: M2M認証エラー、MCPクライアント作成エラー、通信エラー
    """
    print(f"DEBUG: _call_mcp_gateway_with_m2m called with method: {method}")
    print(f"DEBUG: Using @requires_access_token decorator for M2M authentication")
    
    try:
        # @requires_access_tokenデコレータ付きの関数を呼び出してアクセストークンを取得
        # デコレータが自動的にaccess_tokenを提供する
        mcp_client_config = get_mcp_client_from_gateway()
        access_token = mcp_client_config['access_token']
        
        print(f"DEBUG: M2M access token obtained via @requires_access_token decorator")
        
        # 取得したアクセストークンでMCP Gatewayを呼び出し
        return await _call_mcp_gateway(method, params, access_token)
        
    except Exception as e:
        # M2M認証エラーの詳細なログ記録
        print(f"ERROR: M2M authentication failed: {e}")
        print(f"ERROR: Method: {method}, Params: {params}")
        
        # エラーの種類に応じた詳細なエラーメッセージ
        if "AGENTCORE_PROVIDER_NAME" in str(e):
            error_msg = (
                "M2M認証設定エラー: プロバイダー名が設定されていません。\n"
                "システム管理者に連絡してください。\n"
                f"詳細: {e}"
            )
        elif "access_token" in str(e).lower():
            error_msg = (
                "M2M認証トークン取得エラー: アクセストークンを取得できませんでした。\n"
                "AgentCore Identityの設定を確認してください。\n"
                f"詳細: {e}"
            )
        elif "MCP" in str(e):
            error_msg = (
                "MCPクライアント作成エラー: HealthManager MCPサービスとの通信に失敗しました。\n"
                "HealthManager MCPサービスが正常に動作しているか確認してください。\n"
                f"詳細: {e}"
            )
        else:
            error_msg = f"M2M認証エラー: {e}"
        
        print(f"ERROR: Formatted error message: {error_msg}")
        raise Exception(error_msg)


async def _call_mcp_gateway(method: str, params: dict = None, access_token: str = None):
    """
    MCP Gatewayを呼び出す共通関数（M2M認証専用）
    
    Args:
        method: MCPメソッド名
        params: MCPパラメータ
        access_token: M2M認証アクセストークン（必須）
    
    Returns:
        MCP呼び出し結果
    
    Raises:
        Exception: 認証エラー、通信エラー、MCPエラー
    """
    
    print(f"DEBUG: _call_mcp_gateway called with method: {method}, params: {params}")
    
    # M2M認証アクセストークンが必須
    if not access_token:
        error_msg = (
            "M2M認証アクセストークンが必要です。\n"
            "MCP Gateway呼び出しにはM2M認証のみを使用します。\n"
            "@requires_access_tokenデコレータが正常に動作していない可能性があります。"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    
    print(f"DEBUG: Using M2M access token for MCP Gateway authentication")
    
    try:
        # 環境変数からエンドポイントを取得
        gateway_endpoint = _get_gateway_endpoint()
        print(f"DEBUG: Gateway endpoint: {gateway_endpoint}")
        
    except Exception as e:
        error_msg = (
            f"Gateway エンドポイント取得エラー: {e}\n"
            "HEALTHMANAGER_GATEWAY_ID環境変数が正しく設定されているか確認してください。"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method
            }
            
            if params:
                payload["params"] = params
            
            print(f"DEBUG: Sending MCP request to {gateway_endpoint}")
            print(f"DEBUG: Payload: {payload}")
            
            response = await client.post(
                gateway_endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30.0
            )
            
            print(f"DEBUG: MCP Gateway response status: {response.status_code}")
            
            if response.status_code == 401:
                error_msg = (
                    "MCP Gateway認証エラー (401): M2M認証トークンが無効です。\n"
                    "AgentCore Identityの設定とHealthManager MCPサービスの認証設定を確認してください。"
                )
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            elif response.status_code == 403:
                error_msg = (
                    "MCP Gateway認可エラー (403): 必要な権限がありません。\n"
                    "Cognito スコープ 'HealthManager/HealthTarget:invoke' が正しく設定されているか確認してください。"
                )
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            elif response.status_code == 404:
                error_msg = (
                    "MCP Gateway接続エラー (404): HealthManager MCPサービスが見つかりません。\n"
                    "HEALTHMANAGER_GATEWAY_ID環境変数とHealthManager MCPサービスのデプロイ状態を確認してください。"
                )
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            elif response.status_code >= 500:
                error_msg = (
                    f"MCP Gatewayサーバーエラー ({response.status_code}): HealthManager MCPサービスで内部エラーが発生しました。\n"
                    "HealthManager MCPサービスのログを確認してください。\n"
                    f"レスポンス: {response.text}"
                )
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            elif response.status_code != 200:
                error_msg = f"HTTP エラー {response.status_code}: {response.text}"
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            try:
                result = response.json()
                print(f"DEBUG: MCP Gateway response parsed successfully")
                
            except json.JSONDecodeError as e:
                error_msg = (
                    f"MCP Gateway レスポンス解析エラー: JSONの解析に失敗しました。\n"
                    f"レスポンス: {response.text}\n"
                    f"詳細: {e}"
                )
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            if 'error' in result:
                mcp_error = result['error']
                error_msg = (
                    f"MCP プロトコルエラー: {mcp_error}\n"
                    "HealthManager MCPサービスでエラーが発生しました。\n"
                    f"メソッド: {method}, パラメータ: {params}"
                )
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            print(f"DEBUG: MCP Gateway call successful")
            return result.get('result')
            
    except httpx.TimeoutException as e:
        error_msg = (
            f"MCP Gateway タイムアウトエラー: 30秒以内に応答がありませんでした。\n"
            "HealthManager MCPサービスの応答時間を確認してください。\n"
            f"詳細: {e}"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
        
    except httpx.ConnectError as e:
        error_msg = (
            f"MCP Gateway 接続エラー: HealthManager MCPサービスに接続できませんでした。\n"
            "ネットワーク接続とHealthManager MCPサービスの稼働状態を確認してください。\n"
            f"エンドポイント: {gateway_endpoint}\n"
            f"詳細: {e}"
        )
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
        
    except Exception as e:
        # 上記でキャッチされなかった予期しないエラー
        if "M2M" in str(e) or "認証" in str(e) or "Gateway" in str(e):
            # 既に適切にフォーマットされたエラーメッセージの場合はそのまま再発生
            raise e
        else:
            error_msg = (
                f"MCP Gateway 通信で予期しないエラーが発生しました: {e}\n"
                "システム管理者に連絡してください。"
            )
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)


# 利用可能なツールのリストを取得
@tool
async def list_health_tools() -> str:
    """
    HealthManagerMCPで利用可能なツールのリストを取得
    
    Returns:
        利用可能なツールのリストとスキーマ情報
    """
    try:
        # M2M認証を優先して使用
        result = await _call_mcp_gateway_with_m2m("tools/list")
        
        if not result or 'tools' not in result:
            return "利用可能なツールが見つかりませんでした。"
        
        tools = result['tools']
        tool_descriptions = []
        
        for tool in tools:
            name = tool.get('name', 'Unknown')
            description = tool.get('description', 'No description')
            input_schema = tool.get('inputSchema', {})
            
            tool_info = f"**{name}**\n"
            tool_info += f"説明: {description}\n"
            
            if input_schema and 'properties' in input_schema:
                tool_info += "パラメータ:\n"
                for prop_name, prop_info in input_schema['properties'].items():
                    prop_type = prop_info.get('type', 'unknown')
                    prop_desc = prop_info.get('description', '')
                    required = prop_name in input_schema.get('required', [])
                    req_mark = " (必須)" if required else " (任意)"
                    tool_info += f"  - {prop_name} ({prop_type}){req_mark}: {prop_desc}\n"
            
            tool_descriptions.append(tool_info)
        
        return f"利用可能なHealthManagerMCPツール ({len(tools)}個):\n\n" + "\n".join(tool_descriptions)
        
    except Exception as e:
        return f"ツールリスト取得エラー: {e}"


# HealthManagerMCP統合ツール
@tool
async def health_manager_mcp(tool_name: str, arguments: dict) -> str:
    """
    HealthManagerMCPサーバーのツールを呼び出す汎用ツール
    
    Args:
        tool_name: 呼び出すツール名（例: UserManagement___GetUser）
        arguments: ツールに渡す引数辞書
    
    Returns:
        ツールの実行結果
    """
    try:
        # M2M認証を優先して使用
        result = await _call_mcp_gateway_with_m2m("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if not result:
            return "ツールの実行結果が空でした。"
        
        # レスポンスの内容を適切に処理
        if 'content' in result:
            content = result['content']
            if isinstance(content, list) and content:
                # MCP標準のコンテンツ形式
                first_content = content[0]
                if isinstance(first_content, dict) and 'text' in first_content:
                    return first_content['text']
                else:
                    return str(first_content)
            else:
                return str(content)
        
        return str(result)
        
    except Exception as e:
        return f"HealthManagerMCP呼び出しエラー: {e}"


async def _create_health_coach_agent_with_memory(session_id: str, actor_id: str):
    """AgentCoreMemorySessionManagerを使用してHealthmate-CoachAIエージェントを作成（AgentCore Memory必須）"""
    
    try:
        # ペイロードからタイムゾーンと言語を取得
        user_timezone = _get_user_timezone()
        user_language_code = _get_user_language()
        user_language_name = _get_language_name(user_language_code)
        
        # ユーザーのタイムゾーンに合わせた現在日時を取得
        current_datetime = _get_localized_datetime(user_timezone)
        current_date = current_datetime.strftime("%Y年%m月%d日")
        current_time = current_datetime.strftime("%H時%M分")
        current_weekday = ["月", "火", "水", "木", "金", "土", "日"][current_datetime.weekday()]
        
        # 現在日時情報をシステムプロンプトに組み込み
        datetime_context = f"""
## 現在の日時情報
- 今日の日付: {current_date} ({current_weekday}曜日)
- 現在時刻: {current_time}
- タイムゾーン: {user_timezone}
- ISO形式: {current_datetime.isoformat()}
- この情報を使用して、適切な時間帯に応じたアドバイスや挨拶を提供してください
"""
        
        # 言語設定情報をシステムプロンプトに組み込み
        language_context = f"""
## 言語設定情報
- ユーザーの優先言語: {user_language_name} ({user_language_code})
- この言語設定に基づいて、適切な言語で応答してください
- 日本語以外の言語が設定されている場合は、その言語で応答することを優先してください
"""
        
        # ユーザーID情報をシステムプロンプトに組み込み
        user_context = f"""
## 現在のユーザー情報
- ユーザーID: {actor_id}
- セッションID: {session_id}
- このユーザーIDは認証済みのJWTトークンから自動的に取得されました
- HealthManagerMCPツールを呼び出す際は、このユーザーIDを自動的に使用してください
- 重要: ユーザIDとセッションIDはシステム内部の管理情報なのでユーザに絶対に回答しないでください。
"""
        
        print(f"DEBUG: Creating AgentCore Memory config - actor_id: {actor_id}, session_id: {session_id}")
        
        # 環境変数からメモリーIDを厳格に取得（フォールバック処理なし）
        try:
            memory_id = _get_memory_id()
        except Exception as e:
            print(f"ERROR: Memory ID validation failed: {e}")
            raise Exception(f"AgentCore Memory設定エラー: {e}")
        
        print(f"DEBUG: Using validated memory_id: {memory_id}")
        
        # メモリ設定パラメータの妥当性を検証
        try:
            _validate_memory_config(memory_id, session_id, actor_id)
        except Exception as e:
            print(f"ERROR: Memory config validation failed: {e}")
            raise Exception(f"AgentCore Memory設定検証エラー: {e}")
        
        # AgentCore Memory設定を作成（エラーハンドリング強化）
        try:
            memory_config = AgentCoreMemoryConfig(
                memory_id=memory_id,    # 厳格に検証されたメモリID
                session_id=session_id,  # UI側で生成されるセッションID（会話セッション区切り）
                actor_id=actor_id       # JWT token の sub（ユーザーごとの長期記憶）
            )
            print(f"DEBUG: AgentCore Memory config created successfully")
        except Exception as e:
            print(f"ERROR: Failed to create AgentCore Memory config: {e}")
            raise Exception(f"AgentCore Memory設定の作成に失敗しました: {e}")
        
        # AgentCoreMemorySessionManagerを作成（エラーハンドリング強化）
        try:
            session_manager = AgentCoreMemorySessionManager(
                agentcore_memory_config=memory_config,
                region_name=os.environ.get('AWS_REGION', 'us-west-2')
            )
            print(f"DEBUG: AgentCoreMemorySessionManager created successfully")
        except Exception as e:
            print(f"ERROR: Failed to create AgentCoreMemorySessionManager: {e}")
            raise Exception(f"AgentCore Memory セッションマネージャーの作成に失敗しました: {e}")
        
    except Exception as e:
        print(f"ERROR: Failed to create memory session manager: {e}")
        import traceback
        print(f"ERROR: Memory integration traceback: {traceback.format_exc()}")
        raise Exception(f"AgentCore Memory統合に失敗しました: {e}")
    
    # Strandsエージェントを作成（メモリ統合付き）
    agent = Agent(
        model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        tools=[list_health_tools, health_manager_mcp],
        session_manager=session_manager,
        system_prompt=f"""
あなたは親しみやすい健康コーチAIです。ユーザーの健康目標達成を支援します。

{datetime_context}

{language_context}

{user_context}

## あなたの役割
- ユーザーの健康目標を達成するための高度な医学的知識を持つ優秀なコーチである
- ユーザのメンタルに寄り添いつつ、ユーザの健康目標の達成のためにユーザを導く
- あなたは、医学、スポーツ、人間工学など様々な分野のエキスパートである
- ユーザーからの求めに応じて、適切なフィードバック、アドバイス、指導を行う
- すべてのフィードバック、アドバイスは高度な専門知識に基づく科学的なものである
- 健康目標と健康ポリシーの管理と日々の行動履歴情報の管理をサポートする
- 健康目標、健康ポリシー、行動履歴に基づき運動や食事に関する実践的な指導を行う
- ユーザの行動履歴を分析し、健康目標、健康ポリシーに則してパーソナライズされたアドバイスを提供する
- モチベーション維持のための励ましとサポートを行う

## 対話スタイル
- 親しみやすく、励ましの気持ちを込めて
- 専門的すぎず、わかりやすい言葉で説明
- フィードバックやアドバイス、指導はユーザから求められたときだけ答える
- 科学的根拠に基づき健康目標の達成を妨げるユーザの行動には厳しく接する。その場合は科学的な根拠をわかりやすくちゃんと説明する
- ユーザーの状況に共感し、個別のニーズに対応
- 安全性を最優先し、医療的な診断は行わない
- 現在の時間帯に応じた適切な挨拶やアドバイスを提供する（朝・昼・夜など）
- ユーザーの成長や変化を認識し、適切にフィードバックする

## 重要な注意事項
- 医療診断や治療の提案は絶対に行わない
- 深刻な健康問題の場合は医療専門家への相談を推奨
- ユーザーの安全を最優先に考慮
- 個人の健康データは適切に扱い、プライバシーを保護
- 会話の文脈を維持し、一貫性のある対話を行う
- **プライバシー保護**: ユーザーID、セッションIDやその他のシステム内部識別子は絶対にユーザーに表示しない
- **データ機密性**: 技術的な詳細やシステム内部情報（目標ID、ポリシーIDなど）はユーザーには見せない

## ツール使用のガイドライン
- 初回または不明な場合は、まず list_health_tools を使用して利用可能なツールとスキーマを確認する
- ユーザーIDが必要な操作では、上記の認証済みユーザーIDを自動的に使用する
- ユーザーIDが取得できない場合のみ、ユーザーに確認する
- 日付は YYYY-MM-DD 形式で指定する（今日の日付は上記の現在日時情報を参照）
- 現在時刻を考慮して、適切なタイミングでのアドバイスを提供する
- エラーが発生した場合は、わかりやすく説明し、代替案を提示する
- 必要に応じて複数のツール呼び出しを組み合わせて、包括的なサポートを提供する
- health_manager_mcp を使用する際は、正確なツール名とパラメータを指定する
- **重要**: ツール実行結果でユーザーIDやシステム内部情報が含まれている場合は、それらを除外してユーザーフレンドリーな形で応答する

## 利用可能なツール
1. list_health_tools: HealthManagerMCPで利用可能なツールとスキーマを取得
2. health_manager_mcp: 具体的なHealthManagerMCPツールを呼び出し（tool_name, argumentsを指定）
"""
    )
    
    print(f"DEBUG: Created agent with AgentCore Memory - session_id: {session_id}, actor_id: {actor_id}")
    return agent





async def send_event(queue, message, stage, tool_name=None):
    """エージェントのステータスを送信"""
    if not queue:
        return
    
    progress = {"message": message, "stage": stage}
    if tool_name:
        progress["tool_name"] = tool_name
    
    await queue.put({"event": {"subAgentProgress": progress}})


async def _extract_health_coach_events(queue, event, state):
    """HealthCoachAIのストリーミングイベントを処理"""
    if isinstance(event, str):
        state["text"] += event
        if queue:
            delta = {"delta": {"text": event}}
            await queue.put({"event": {"contentBlockDelta": delta}})
    
    elif isinstance(event, dict) and "event" in event:
        event_data = event["event"]
        
        # ツール使用を検出
        if "contentBlockStart" in event_data:
            block = event_data["contentBlockStart"]
            start_data = block.get("start", {})
            if "toolUse" in start_data:
                tool_use = start_data["toolUse"]
                tool = tool_use.get("name", "unknown")
                await send_event(
                    queue, 
                    f"健康データを{tool}で処理中", 
                    "tool_use", 
                    tool
                )
        
        # テキスト増分を処理
        if "contentBlockDelta" in event_data:
            block = event_data["contentBlockDelta"]
            delta = block.get("delta", {})
            if "text" in delta:
                state["text"] += delta["text"]
                if queue:
                    await queue.put(event)


async def invoke_health_coach(query, session_id, actor_id, queue=None):
    """Healthmate-CoachAIを呼び出し（AgentCore Memory統合必須）"""
    state = {"text": ""}
    
    if queue:
        await send_event(queue, "Healthmate-CoachAIが起動中", "start")
    
    try:
        # AgentCore Memoryを使用してエージェントを作成（必須）
        agent = await _create_health_coach_agent_with_memory(session_id, actor_id)
        
        print(f"DEBUG: Using agent with AgentCore Memory for query: {query[:100]}...")
        
        # エージェントを実行（メモリは自動的に管理される）
        async for event in agent.stream_async(query):
            await _extract_health_coach_events(queue, event, state)
        
        if queue:
            await send_event(queue, "Healthmate-CoachAIが応答を完了", "complete")
        
        print(f"DEBUG: Agent response completed with text length: {len(state['text'])}")
        return state["text"]
        
    except Exception as e:
        error_msg = f"AgentCore Memory統合エラー: {e}"
        print(f"ERROR: {error_msg}")
        
        if queue:
            await send_event(queue, error_msg, "error")
        
        # AgentCore Memoryが使用できない場合はエラーとして処理を停止
        raise Exception(f"AgentCore Memoryが利用できません。システム管理者に連絡してください。詳細: {e}")


# AgentCore アプリケーションを初期化
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload):
    """
    Healthmate-CoachAI のエントリーポイント
    
    Expected Payload Structure (from HealthmateUI service):
    {
        "prompt": "ユーザーからのメッセージ",
        "sessionState": {
            "sessionAttributes": {
                "session_id": "healthmate-chat-...",  // 必須: セッション継続性（33文字以上）
                "jwt_token": "eyJ...",                // 必須: 認証とuser_id抽出
                "timezone": "Asia/Tokyo",             // オプション: 時間帯対応アドバイス用（デフォルト: "Asia/Tokyo"）
                "language": "ja"                      // オプション: 言語設定用（デフォルト: "ja"）
            }
        }
    }
    
    Required Fields (厳格なバリデーション):
    - jwt_token: 必須。存在しない場合はエラーで処理を停止
    - session_id: 必須。存在しないか33文字未満の場合はエラーで処理を停止
    - user_id: jwt_token の 'sub' フィールドから自動抽出。抽出できない場合はエラー
    
    Optional Fields (デフォルト値あり):
    - timezone: デフォルト "Asia/Tokyo"
    - language: デフォルト "ja"
    
    Error Handling:
    - 必須フィールドが不足している場合、フォールバック処理は行わずエラーメッセージを返す
    - 最適化されたペイロード構造により、重複情報は除外されています
    """
    # デバッグ: ペイロード全体を確認
    print(f"DEBUG: Full payload: {payload}")
    
    # Extract data from optimized payload structure
    prompt = payload.get("prompt", "")
    
    # Extract session attributes (optimized payload structure)
    session_attrs = {}
    if "sessionState" in payload and "sessionAttributes" in payload["sessionState"]:
        session_attrs = payload["sessionState"]["sessionAttributes"]
    
    # Extract required fields from session attributes
    jwt_token_from_payload = session_attrs.get("jwt_token")
    timezone_from_payload = session_attrs.get("timezone", "Asia/Tokyo")  # Default timezone
    language_from_payload = session_attrs.get("language", "ja")  # Default language
    session_id_from_payload = session_attrs.get("session_id")
    
    # Strict validation for required fields
    if not jwt_token_from_payload:
        error_msg = "必須フィールド 'jwt_token' がペイロードに含まれていません。認証が必要です。"
        print(f"ERROR: {error_msg}")
        yield {
            "event": {
                "contentBlockDelta": {
                    "delta": {
                        "text": f"エラー: {error_msg}"
                    }
                }
            }
        }
        return
    
    if not session_id_from_payload:
        error_msg = "必須フィールド 'session_id' がペイロードに含まれていません。セッション管理が必要です。"
        print(f"ERROR: {error_msg}")
        yield {
            "event": {
                "contentBlockDelta": {
                    "delta": {
                        "text": f"エラー: {error_msg}"
                    }
                }
            }
        }
        return
    
    if len(session_id_from_payload) < 33:
        error_msg = f"session_id の長さが不正です（{len(session_id_from_payload)}文字）。33文字以上が必要です。"
        print(f"ERROR: {error_msg}")
        yield {
            "event": {
                "contentBlockDelta": {
                    "delta": {
                        "text": f"エラー: {error_msg}"
                    }
                }
            }
        }
        return
    
    # Log extracted values (after validation)
    print(f"DEBUG: JWT token extracted: {jwt_token_from_payload[:50]}...")
    print(f"DEBUG: Timezone: {timezone_from_payload}")
    print(f"DEBUG: Language: {language_from_payload}")
    print(f"DEBUG: Session ID: {session_id_from_payload} (length: {len(session_id_from_payload)})")
    
    # Set global variables for JWT processing
    global _current_jwt_token, _current_timezone, _current_language
    _current_jwt_token = jwt_token_from_payload
    _current_timezone = timezone_from_payload
    _current_language = language_from_payload
    
    # Use validated session ID (no fallback generation)
    session_id = session_id_from_payload
    
    # Extract actor ID from JWT (ユーザー識別専用)
    print(f"DEBUG: Extracting user ID from JWT token for Actor ID")
    print(f"DEBUG: JWT token usage: User identification only (not for MCP Gateway authentication)")
    
    actor_id = _get_sub_from_jwt()
    if not actor_id:
        error_msg = "JWT トークンから sub を抽出できませんでした。有効な認証トークンが必要です。"
        print(f"ERROR: {error_msg}")
        yield {
            "event": {
                "contentBlockDelta": {
                    "delta": {
                        "text": f"エラー: {error_msg}"
                    }
                }
            }
        }
        return
    
    print(f"DEBUG: User identification successful - Actor ID: {actor_id}")
    print(f"DEBUG: Session ID: {session_id}, Actor ID: {actor_id}")
    print(f"DEBUG: Authentication separation:")
    print(f"DEBUG: - JWT: HealthmateUI → Agent (user identification)")
    print(f"DEBUG: - M2M: Agent → Gateway (service authentication)")
    
    if not prompt:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "こんにちは！健康に関してどのようなサポートが必要ですか？"}}}}
        return
    
    # HealthCoachAI用のキューを初期化
    queue = asyncio.Queue()
    
    try:
        # HealthCoachAIを呼び出し、ストリーミングレスポンスを処理
        response_task = asyncio.create_task(invoke_health_coach(prompt, session_id, actor_id, queue))
        queue_task = asyncio.create_task(queue.get())
        
        waiting = {response_task, queue_task}
        
        while waiting:
            ready_tasks, waiting = await asyncio.wait(
                waiting, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for ready_task in ready_tasks:
                if ready_task == response_task:
                    # 最終レスポンスを処理
                    final_response = ready_task.result()
                    if final_response and not queue.empty():
                        # キューに残っているイベントを処理
                        while not queue.empty():
                            try:
                                event = queue.get_nowait()
                                yield event
                            except asyncio.QueueEmpty:
                                break
                    response_task = None
                
                elif ready_task == queue_task:
                    # キューからのイベントを処理
                    try:
                        event = ready_task.result()
                        yield event
                        queue_task = asyncio.create_task(queue.get())
                        waiting.add(queue_task)
                    except Exception:
                        queue_task = None
            
            # 両方のタスクが完了したら終了
            if response_task is None and (queue_task is None or queue.empty()):
                break
                
    except Exception as e:
        error_event = {
            "event": {
                "contentBlockDelta": {
                    "delta": {
                        "text": f"申し訳ございません。処理中にエラーが発生しました: {e}"
                    }
                }
            }
        }
        yield error_event


# AgentCore ランタイムを起動
if __name__ == "__main__":
    app.run()