"""
HealthCoachAI エージェント

Amazon Bedrock AgentCore Runtime上で動作する
健康支援AIエージェントです。
"""

import os
import asyncio
import httpx
import boto3
import json
import base64
from datetime import datetime
from typing import Optional
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext


# CloudFormation設定管理
class CloudFormationConfig:
    """CloudFormationスタックから動的に設定を取得"""
    
    def __init__(self):
        self._gateway_id: Optional[str] = None
        self._region: Optional[str] = None
        self._gateway_endpoint: Optional[str] = None
    
    def _get_stack_name(self) -> str:
        """スタック名を環境変数または デフォルト値から取得"""
        return os.environ.get('HEALTH_STACK_NAME', 'HealthManagerMCPStack')
    
    def _get_region(self) -> str:
        """AWSリージョンを取得"""
        if self._region is None:
            # 環境変数、AWS設定、デフォルトの順で取得
            self._region = (
                os.environ.get('AWS_REGION') or 
                os.environ.get('AWS_DEFAULT_REGION') or
                boto3.Session().region_name or
                'us-west-2'
            )
        return self._region
    
    def _fetch_cloudformation_outputs(self) -> dict:
        """CloudFormationスタックの出力を取得"""
        try:
            stack_name = self._get_stack_name()
            region = self._get_region()
            
            cfn = boto3.client('cloudformation', region_name=region)
            response = cfn.describe_stacks(StackName=stack_name)
            
            if not response['Stacks']:
                raise Exception(f"CloudFormationスタック '{stack_name}' が見つかりません")
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            return outputs
            
        except Exception as e:
            # CloudFormation取得に失敗した場合はデフォルト値を使用
            print(f"CloudFormation設定取得エラー（デフォルト値を使用）: {e}")
            return {
                'GatewayId': os.environ.get('HEALTH_GATEWAY_ID', 'CONFIGURE_GATEWAY_ID'),
                'Region': self._get_region()
            }
    
    def get_gateway_id(self) -> str:
        """Gateway IDを取得"""
        if self._gateway_id is None:
            outputs = self._fetch_cloudformation_outputs()
            self._gateway_id = outputs.get('GatewayId', os.environ.get('HEALTH_GATEWAY_ID', 'CONFIGURE_GATEWAY_ID'))
        return self._gateway_id
    
    def get_gateway_endpoint(self) -> str:
        """Gateway エンドポイントを取得"""
        if self._gateway_endpoint is None:
            gateway_id = self.get_gateway_id()
            region = self._get_region()
            self._gateway_endpoint = f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"
        return self._gateway_endpoint


# グローバル設定インスタンス
_config = CloudFormationConfig()

# グローバルJWTトークン（一時的なハック）
_current_jwt_token = None


# JWT Token ヘルパー関数
def _decode_jwt_payload(jwt_token: str) -> dict:
    """JWTトークンのペイロードをデコード（署名検証なし）"""
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
    """JWT認証トークンを取得（同期版）"""
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


def _get_user_id_from_jwt():
    """JWTトークンからユーザーIDを取得（同期版）"""
    try:
        jwt_token = _get_jwt_token()
        if not jwt_token:
            print(f"DEBUG: No JWT token available for user ID extraction")
            return None
        
        payload = _decode_jwt_payload(jwt_token)
        user_id = payload.get('sub')  # Cognitoの場合、subフィールドにユーザーIDが含まれる
        
        print(f"DEBUG: Extracted user ID from JWT: {user_id}")
        return user_id
        
    except Exception as e:
        print(f"DEBUG: ユーザーID取得エラー: {e}")
        return None


async def _call_mcp_gateway(method: str, params: dict = None):
    """MCP Gatewayを呼び出す共通関数"""
    jwt_token = _get_jwt_token()
    
    print(f"DEBUG: _call_mcp_gateway called with method: {method}, params: {params}")
    print(f"DEBUG: JWT token available: {'Yes' if jwt_token else 'No'}")
    
    if not jwt_token:
        raise Exception("認証トークンが見つかりません。HealthMate UIから適切に認証されていることを確認してください。")
    
    # CloudFormationから動的にエンドポイントを取得
    gateway_endpoint = _config.get_gateway_endpoint()
    print(f"DEBUG: Gateway endpoint: {gateway_endpoint}")
    
    async with httpx.AsyncClient() as client:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method
        }
        
        if params:
            payload["params"] = params
        
        response = await client.post(
            gateway_endpoint,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP エラー {response.status_code}: {response.text}")
        
        result = response.json()
        if 'error' in result:
            raise Exception(f"MCP エラー: {result['error']}")
        
        return result.get('result')


# 利用可能なツールのリストを取得
@tool
async def list_health_tools() -> str:
    """
    HealthManagerMCPで利用可能なツールのリストを取得
    
    Returns:
        利用可能なツールのリストとスキーマ情報
    """
    try:
        result = await _call_mcp_gateway("tools/list")
        
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
        result = await _call_mcp_gateway("tools/call", {
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


async def _create_health_coach_agent():
    """HealthCoachAIエージェントを作成（ユーザーID自動設定付き）"""
    
    # JWTトークンからユーザーIDを取得
    user_id = _get_user_id_from_jwt()
    
    # 現在日時を取得
    current_datetime = datetime.now()
    current_date = current_datetime.strftime("%Y年%m月%d日")
    current_time = current_datetime.strftime("%H時%M分")
    current_weekday = ["月", "火", "水", "木", "金", "土", "日"][current_datetime.weekday()]
    
    # 現在日時情報をシステムプロンプトに組み込み
    datetime_context = f"""
## 現在の日時情報
- 今日の日付: {current_date} ({current_weekday}曜日)
- 現在時刻: {current_time}
- ISO形式: {current_datetime.isoformat()}
- この情報を使用して、適切な時間帯に応じたアドバイスや挨拶を提供してください
"""
    
    # ユーザーID情報をシステムプロンプトに組み込み
    user_context = ""
    if user_id:
        user_context = f"""
## 現在のユーザー情報
- ユーザーID: {user_id}
- このユーザーIDは認証済みのJWTトークンから自動的に取得されました
- HealthManagerMCPツールを呼び出す際は、このユーザーIDを自動的に使用してください
"""
    else:
        user_context = """
## 現在のユーザー情報
- ユーザーIDが取得できませんでした
- HealthManagerMCPツールを使用する前に、ユーザーにユーザーIDの確認を求めてください
"""
    
    return Agent(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        tools=[list_health_tools, health_manager_mcp],
        system_prompt=f"""
あなたは親しみやすい健康コーチAIです。ユーザーの健康目標達成を支援します。

{datetime_context}

{user_context}

## あなたの役割
- ユーザーの健康データを分析し、パーソナライズされたアドバイスを提供
- 健康目標の設定と進捗追跡をサポート
- 運動や食事に関する実践的な指導
- モチベーション維持のための励ましとサポート

## 対話スタイル
- 親しみやすく、励ましの気持ちを込めて
- 専門的すぎず、わかりやすい言葉で説明
- ユーザーの状況に共感し、個別のニーズに対応
- 安全性を最優先し、医療的な診断は行わない
- 現在の時間帯に応じた適切な挨拶やアドバイスを提供する（朝・昼・夜など）

## 重要な注意事項
- 医療診断や治療の提案は絶対に行わない
- 深刻な健康問題の場合は医療専門家への相談を推奨
- ユーザーの安全を最優先に考慮
- 個人の健康データは適切に扱い、プライバシーを保護

## ツール使用のガイドライン
- 初回または不明な場合は、まず list_health_tools を使用して利用可能なツールとスキーマを確認する
- ユーザーIDが必要な操作では、上記の認証済みユーザーIDを自動的に使用する
- ユーザーIDが取得できない場合のみ、ユーザーに確認する
- 日付は YYYY-MM-DD 形式で指定する（今日の日付は上記の現在日時情報を参照）
- 現在時刻を考慮して、適切なタイミングでのアドバイスを提供する
- エラーが発生した場合は、わかりやすく説明し、代替案を提示する
- 必要に応じて複数のツール呼び出しを組み合わせて、包括的なサポートを提供する
- health_manager_mcp を使用する際は、正確なツール名とパラメータを指定する

## 利用可能なツール
1. list_health_tools: HealthManagerMCPで利用可能なツールとスキーマを取得
2. health_manager_mcp: 具体的なHealthManagerMCPツールを呼び出し（tool_name, argumentsを指定）
"""
    )


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


async def invoke_health_coach(query, queue=None):
    """HealthCoachAIを呼び出し"""
    state = {"text": ""}
    
    if queue:
        await send_event(queue, "HealthCoachAIが起動中", "start")
    
    try:
        # エージェントを作成（ユーザーID自動設定付き）
        agent = await _create_health_coach_agent()
        if not agent:
            return "HealthCoachAIエージェントの初期化に失敗しました。"
        
        # エージェントを実行
        async for event in agent.stream_async(query):
            await _extract_health_coach_events(queue, event, state)
        
        if queue:
            await send_event(queue, "HealthCoachAIが応答を完了", "complete")
        
        return state["text"]
        
    except Exception as e:
        error_msg = f"HealthCoachAIの処理中にエラーが発生しました: {e}"
        if queue:
            await send_event(queue, error_msg, "error")
        return error_msg


# AgentCore アプリケーションを初期化
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload):
    """HealthCoachAI のエントリーポイント"""
    # デバッグ: ペイロード全体を確認
    print(f"DEBUG: Full payload: {payload}")
    
    prompt = payload.get("input", {}).get("prompt", "")
    
    # 別の可能性も試す
    if not prompt:
        prompt = payload.get("prompt", "")
    if not prompt:
        prompt = payload.get("message", "")
    
    # JWTトークンをペイロードから直接取得を試行
    jwt_token_from_payload = None
    
    # 様々な場所からJWTトークンを探す
    if "jwt_token" in payload:
        jwt_token_from_payload = payload["jwt_token"]
        print(f"DEBUG: JWT token from payload.jwt_token: {jwt_token_from_payload[:50]}...")
    elif "input" in payload and isinstance(payload["input"], dict) and "jwt_token" in payload["input"]:
        jwt_token_from_payload = payload["input"]["jwt_token"]
        print(f"DEBUG: JWT token from payload.input.jwt_token: {jwt_token_from_payload[:50]}...")
    elif "sessionState" in payload and "sessionAttributes" in payload["sessionState"]:
        session_attrs = payload["sessionState"]["sessionAttributes"]
        if "jwt_token" in session_attrs:
            jwt_token_from_payload = session_attrs["jwt_token"]
            print(f"DEBUG: JWT token from sessionState: {jwt_token_from_payload[:50]}...")
    
    # さらに詳細な検索
    if not jwt_token_from_payload:
        print(f"DEBUG: Searching for JWT token in all payload keys...")
        def search_jwt_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if key == "jwt_token" and isinstance(value, str) and len(value) > 50:
                        print(f"DEBUG: Found JWT token at {current_path}: {value[:50]}...")
                        return value
                    elif isinstance(value, (dict, list)):
                        result = search_jwt_recursive(value, current_path)
                        if result:
                            return result
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    result = search_jwt_recursive(item, current_path)
                    if result:
                        return result
            return None
        
        jwt_token_from_payload = search_jwt_recursive(payload)
    
    # グローバル変数にJWTトークンを設定（一時的なハック）
    if jwt_token_from_payload:
        global _current_jwt_token
        _current_jwt_token = jwt_token_from_payload
        print(f"DEBUG: Set global JWT token: {jwt_token_from_payload[:50]}...")
    else:
        print(f"DEBUG: No JWT token found in payload")
    
    if not prompt:
        yield {"event": {"contentBlockDelta": {"delta": {"text": "こんにちは！健康に関してどのようなサポートが必要ですか？"}}}}
        return
    
    # HealthCoachAI用のキューを初期化
    queue = asyncio.Queue()
    
    try:
        # HealthCoachAIを呼び出し、ストリーミングレスポンスを処理
        response_task = asyncio.create_task(invoke_health_coach(prompt, queue))
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