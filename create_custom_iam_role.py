#!/usr/bin/env python3
"""
Healthmate-CoachAI用カスタムIAMロール作成スクリプト

AgentCore Runtime用の適切な権限を持つカスタムIAMロールを作成します。
"""

import boto3
import json
import sys
import time
from botocore.exceptions import ClientError


def load_policy_document(file_path: str) -> dict:
    """ポリシードキュメントをファイルから読み込み"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ ポリシーファイル読み込みエラー ({file_path}): {e}")
        sys.exit(1)


def create_iam_role_and_policies():
    """カスタムIAMロールとポリシーを作成"""
    
    # AWS設定
    region = 'us-west-2'
    account_id = boto3.client('sts').get_caller_identity()['Account']
    role_name = 'Healthmate-CoachAI-AgentCore-Runtime-Role'
    
    print("=" * 80)
    print("🔐 Healthmate-CoachAI用カスタムIAMロール作成")
    print("=" * 80)
    print(f"📍 リージョン: {region}")
    print(f"🏢 アカウントID: {account_id}")
    print(f"🎭 ロール名: {role_name}")
    print()
    
    # IAMクライアント初期化
    iam = boto3.client('iam', region_name=region)
    
    try:
        # 1. 信頼ポリシーを読み込み
        print("📋 信頼ポリシーを読み込み中...")
        trust_policy = load_policy_document('agentcore-trust-policy.json')
        
        # 2. IAMロールを作成
        print(f"🎭 IAMロール '{role_name}' を作成中...")
        try:
            iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Healthmate-CoachAI AgentCore Runtime Custom Role',
                MaxSessionDuration=3600
            )
            print(f"   ✅ IAMロール作成完了")
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"   ⚠️  IAMロール '{role_name}' は既に存在します")
            else:
                raise
        
        # 3. ポリシーを作成・アタッチ
        policies = [
            {
                'name': 'Healthmate-CoachAI-AgentCore-Runtime-Policy',
                'file': 'bedrock-agentcore-runtime-policy.json',
                'description': 'AgentCore Runtime Basic Permissions'
            }
        ]
        
        for policy_info in policies:
            policy_name = policy_info['name']
            policy_file = policy_info['file']
            policy_description = policy_info['description']
            
            print(f"📜 ポリシー '{policy_name}' を作成中...")
            
            # ポリシードキュメントを読み込み
            policy_document = load_policy_document(policy_file)
            policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
            
            try:
                # ポリシーを作成
                iam.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document),
                    Description=policy_description
                )
                print(f"   ✅ ポリシー作成完了: {policy_arn}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    print(f"   ⚠️  ポリシー '{policy_name}' は既に存在します")
                else:
                    raise
            
            # ロールにポリシーをアタッチ
            print(f"🔗 ポリシーをロールにアタッチ中...")
            try:
                iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                print(f"   ✅ ポリシーアタッチ完了")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"   ⚠️  ロールまたはポリシーが見つかりません")
                else:
                    print(f"   ⚠️  ポリシーアタッチエラー: {e}")
        
        # 4. ロール作成完了を待機
        print("⏳ IAMロールの作成完了を待機中...")
        time.sleep(10)  # IAMの整合性確保のため少し待機
        
        # 5. 作成されたロールの詳細を表示
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        print()
        print("✅ カスタムIAMロール作成完了！")
        print()
        print("📋 作成されたリソース:")
        print(f"   🎭 ロール名: {role_name}")
        print(f"   🔗 ロールARN: {role_arn}")
        print()
        print("📜 アタッチされたポリシー:")
        for policy_info in policies:
            policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_info['name']}"
            print(f"   - {policy_info['name']}")
            print(f"     ARN: {policy_arn}")
        print()
        print("🚀 次のステップ:")
        print("   deploy_to_aws.sh を実行してエージェントをデプロイしてください")
        print(f"   このロールARNが自動的に使用されます: {role_arn}")
        print()
        
        return role_arn
        
    except Exception as e:
        print(f"❌ IAMロール作成エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    create_iam_role_and_policies()