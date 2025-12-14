#!/usr/bin/env python3
"""
AgentCore Runtime IAM権限設定スクリプト（レガシー版）

⚠️  注意: このスクリプトはレガシー版です。
新しいデプロイでは create_custom_iam_role.py と deploy_to_aws.sh を使用してください。

既存のAgentCore Runtime実行ロールに権限を後から追加する場合のみ使用してください。
"""

import boto3
import json
import sys
import yaml
from botocore.exceptions import ClientError


def load_agentcore_config():
    """AgentCore設定ファイルから実行ロールARNを取得"""
    try:
        with open('.bedrock_agentcore.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        execution_role_arn = config['agents']['health_coach_ai']['aws']['execution_role']
        account_id = config['agents']['health_coach_ai']['aws']['account']
        region = config['agents']['health_coach_ai']['aws']['region']
        
        return execution_role_arn, account_id, region
    
    except Exception as e:
        print(f"❌ AgentCore設定ファイル読み込みエラー: {e}")
        return None, None, None


def load_policy_document(file_path):
    """IAMポリシードキュメントをファイルから読み込み"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ ポリシーファイル読み込みエラー ({file_path}): {e}")
        return None


def attach_policy_to_role(iam_client, role_name, policy_name, policy_document):
    """IAMロールにインラインポリシーを追加"""
    try:
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"   ✅ ポリシー '{policy_name}' を正常に追加しました")
        return True
    
    except ClientError as e:
        print(f"   ❌ ポリシー '{policy_name}' 追加エラー: {e}")
        return False


def check_existing_policies(iam_client, role_name):
    """既存のインラインポリシーを確認"""
    try:
        response = iam_client.list_role_policies(RoleName=role_name)
        return response['PolicyNames']
    except ClientError as e:
        print(f"❌ 既存ポリシー確認エラー: {e}")
        return []


def main():
    """メイン処理"""
    print("🔧 AgentCore Runtime IAM権限設定スクリプト")
    print("=" * 60)
    
    # AgentCore設定を読み込み
    print("📋 AgentCore設定を確認中...")
    execution_role_arn, account_id, region = load_agentcore_config()
    
    if not execution_role_arn:
        print("❌ AgentCore設定の読み込みに失敗しました")
        sys.exit(1)
    
    # ロール名を抽出
    role_name = execution_role_arn.split('/')[-1]
    
    print(f"   実行ロールARN: {execution_role_arn}")
    print(f"   ロール名: {role_name}")
    print(f"   アカウントID: {account_id}")
    print(f"   リージョン: {region}")
    
    # IAMクライアント初期化
    try:
        iam_client = boto3.client('iam', region_name=region)
        print(f"   ✅ IAMクライアント初期化完了 (リージョン: {region})")
    except Exception as e:
        print(f"❌ IAMクライアント初期化エラー: {e}")
        sys.exit(1)
    
    # 既存ポリシーを確認
    print("\n🔍 既存のインラインポリシーを確認中...")
    existing_policies = check_existing_policies(iam_client, role_name)
    if existing_policies:
        print(f"   既存ポリシー: {', '.join(existing_policies)}")
    else:
        print("   既存のインラインポリシーはありません")
    
    # 必要なポリシーを定義
    policies_to_add = [
        {
            'name': 'HealthCoachAI-CloudFormation-ReadAccess',
            'file': 'cloudformation-read-policy.json',
            'description': 'CloudFormationスタック情報読み取り権限'
        },
        {
            'name': 'HealthCoachAI-Cognito-ReadAccess', 
            'file': 'cognito-read-policy.json',
            'description': 'Cognito設定読み取り権限'
        }
    ]
    
    print(f"\n🚀 必要なポリシーを追加中...")
    
    success_count = 0
    for policy_info in policies_to_add:
        policy_name = policy_info['name']
        policy_file = policy_info['file']
        description = policy_info['description']
        
        print(f"\n   📝 {description}")
        print(f"      ポリシー名: {policy_name}")
        print(f"      ファイル: {policy_file}")
        
        # 既に存在するかチェック
        if policy_name in existing_policies:
            print(f"      ⚠️  ポリシー '{policy_name}' は既に存在します（スキップ）")
            success_count += 1
            continue
        
        # ポリシードキュメントを読み込み
        policy_document = load_policy_document(policy_file)
        if not policy_document:
            continue
        
        # ポリシーを追加
        if attach_policy_to_role(iam_client, role_name, policy_name, policy_document):
            success_count += 1
    
    # 結果サマリー
    print(f"\n📊 結果サマリー:")
    print(f"   追加対象ポリシー数: {len(policies_to_add)}")
    print(f"   成功: {success_count}")
    print(f"   失敗: {len(policies_to_add) - success_count}")
    
    if success_count == len(policies_to_add):
        print(f"\n✅ すべてのポリシーが正常に設定されました！")
        print(f"\n🚀 次のステップ:")
        print(f"   1. AgentCore Runtimeを再起動してください:")
        print(f"      agentcore deploy")
        print(f"   2. manual_test_deployed_agent.py でテストしてください")
        print(f"   3. MCP Gateway接続が正常に動作することを確認してください")
    else:
        print(f"\n❌ 一部のポリシー設定に失敗しました")
        print(f"   手動でIAMコンソールから権限を確認してください")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 スクリプトが中断されました")
    except Exception as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)