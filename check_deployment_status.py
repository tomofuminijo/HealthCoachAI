#!/usr/bin/env python3
"""
HealthCoachAI デプロイ状態確認スクリプト

AWSにデプロイされたHealthCoachAIエージェントの状態を確認します。
"""

import boto3
import json
from datetime import datetime
from test_config_helper import test_config


def print_banner():
    """バナー表示"""
    print("=" * 80)
    print("📊 HealthCoachAI デプロイ状態確認")
    print("=" * 80)
    print()


def format_datetime(dt_string):
    """日時文字列をフォーマット"""
    try:
        if isinstance(dt_string, datetime):
            return dt_string.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt_string)
    except:
        return str(dt_string)


def check_agent_status():
    """エージェントの状態を確認"""
    try:
        config = test_config.get_all_config()
        client = boto3.client('bedrock-agentcore', region_name=config['region'])
        
        print("🔍 エージェント一覧を取得中...")
        
        # エージェント一覧を取得
        response = client.list_agents()
        agents = response.get('agentSummaries', [])
        
        if not agents:
            print("❌ デプロイされたエージェントが見つかりません")
            return False
        
        print(f"✅ {len(agents)} 個のエージェントが見つかりました")
        print()
        
        # health-coach-ai エージェントを検索
        health_coach_agent = None
        for agent in agents:
            print(f"📋 エージェント: {agent.get('agentName', 'Unknown')}")
            print(f"   ID: {agent.get('agentId', 'Unknown')}")
            print(f"   状態: {agent.get('agentStatus', 'Unknown')}")
            print(f"   作成日時: {format_datetime(agent.get('createdAt', 'Unknown'))}")
            print(f"   更新日時: {format_datetime(agent.get('updatedAt', 'Unknown'))}")
            
            if agent.get('agentName') == 'health-coach-ai':
                health_coach_agent = agent
                print("   🎯 ← これがHealthCoachAIエージェントです")
            
            print()
        
        if not health_coach_agent:
            print("❌ health-coach-ai エージェントが見つかりません")
            return False
        
        agent_id = health_coach_agent['agentId']
        
        # エージェントの詳細情報を取得
        print("🔍 エージェント詳細情報を取得中...")
        detail_response = client.get_agent(agentId=agent_id)
        agent_detail = detail_response.get('agent', {})
        
        print("📋 HealthCoachAI エージェント詳細:")
        print(f"   名前: {agent_detail.get('agentName', 'Unknown')}")
        print(f"   ID: {agent_detail.get('agentId', 'Unknown')}")
        print(f"   状態: {agent_detail.get('agentStatus', 'Unknown')}")
        print(f"   バージョン: {agent_detail.get('agentVersion', 'Unknown')}")
        print(f"   説明: {agent_detail.get('description', 'なし')}")
        print(f"   作成日時: {format_datetime(agent_detail.get('createdAt', 'Unknown'))}")
        print(f"   更新日時: {format_datetime(agent_detail.get('updatedAt', 'Unknown'))}")
        print()
        
        # エージェントエイリアス一覧を取得
        print("🔍 エージェントエイリアス一覧を取得中...")
        alias_response = client.list_agent_aliases(agentId=agent_id)
        aliases = alias_response.get('agentAliasSummaries', [])
        
        if not aliases:
            print("❌ エージェントエイリアスが見つかりません")
            return False
        
        print(f"✅ {len(aliases)} 個のエイリアスが見つかりました")
        print()
        
        for alias in aliases:
            print(f"📋 エイリアス: {alias.get('agentAliasName', 'Unknown')}")
            print(f"   ID: {alias.get('agentAliasId', 'Unknown')}")
            print(f"   状態: {alias.get('agentAliasStatus', 'Unknown')}")
            print(f"   作成日時: {format_datetime(alias.get('createdAt', 'Unknown'))}")
            print(f"   更新日時: {format_datetime(alias.get('updatedAt', 'Unknown'))}")
            print()
        
        # 設定情報も表示
        print("⚙️  CloudFormation設定:")
        print(f"   スタック名: {config.get('stack_name', 'Unknown')}")
        print(f"   リージョン: {config.get('region', 'Unknown')}")
        print(f"   User Pool ID: {config.get('user_pool_id', 'Unknown')}")
        print(f"   Client ID: {config.get('client_id', 'Unknown')}")
        print()
        
        print("✅ HealthCoachAIエージェントは正常にデプロイされています！")
        print()
        print("🧪 テスト方法:")
        print("   python manual_test_deployed_agent.py")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン関数"""
    print_banner()
    
    success = check_agent_status()
    
    if success:
        print("🎉 すべての確認が完了しました！")
    else:
        print("⚠️  問題が検出されました。デプロイ状態を確認してください。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 確認が中断されました。")
    except Exception as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()