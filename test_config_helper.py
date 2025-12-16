#!/usr/bin/env python3
"""
テスト用設定ヘルパー

CloudFormationスタックから動的に設定を取得し、
テストファイルで共通利用できるようにします。
"""

import boto3
import json
from botocore.exceptions import ClientError


class TestConfig:
    """テスト用設定管理クラス"""
    
    def __init__(self):
        self._config = None
    
    def _get_stack_name(self) -> str:
        """CloudFormationスタック名を取得"""
        import os
        return os.environ.get('HEALTH_STACK_NAME', 'Healthmate-HealthManagerStack')
    
    def _get_region(self) -> str:
        """AWSリージョンを取得"""
        import os
        return (
            os.environ.get('AWS_REGION') or 
            os.environ.get('AWS_DEFAULT_REGION') or
            boto3.Session().region_name or
            'us-west-2'
        )
    
    def _fetch_cloudformation_config(self) -> dict:
        """CloudFormationスタックから設定を取得"""
        try:
            stack_name = self._get_stack_name()
            region = self._get_region()
            
            print(f"CloudFormation設定取得中: スタック={stack_name}, リージョン={region}")
            
            cfn = boto3.client('cloudformation', region_name=region)
            response = cfn.describe_stacks(StackName=stack_name)
            
            if not response['Stacks']:
                raise Exception(f"CloudFormationスタック '{stack_name}' が見つかりません")
            
            outputs = {}
            for output in response['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            print(f"CloudFormation出力: {list(outputs.keys())}")
            
            # 必要な出力が存在するかチェック
            required_outputs = ['UserPoolId', 'UserPoolClientId', 'GatewayId']
            missing_outputs = [key for key in required_outputs if key not in outputs]
            if missing_outputs:
                raise Exception(f"必要なCloudFormation出力が見つかりません: {missing_outputs}")
            
            # Cognito Client Secretを取得
            cognito_client = boto3.client('cognito-idp', region_name=region)
            client_response = cognito_client.describe_user_pool_client(
                UserPoolId=outputs['UserPoolId'],
                ClientId=outputs['UserPoolClientId']
            )
            client_secret = client_response['UserPoolClient']['ClientSecret']
            
            config = {
                'region': region,
                'user_pool_id': outputs['UserPoolId'],
                'client_id': outputs['UserPoolClientId'],
                'client_secret': client_secret,
                'gateway_id': outputs['GatewayId']
            }
            
            print("✅ CloudFormation設定取得完了")
            return config
            
        except Exception as e:
            print(f"❌ CloudFormation設定取得エラー: {e}")
            raise
    
    def get_all_config(self) -> dict:
        """すべての設定を取得（キャッシュ付き）"""
        if self._config is None:
            self._config = self._fetch_cloudformation_config()
        return self._config
    
    def get_cognito_config(self) -> dict:
        """Cognito設定のみを取得"""
        config = self.get_all_config()
        return {
            'region': config['region'],
            'user_pool_id': config['user_pool_id'],
            'client_id': config['client_id'],
            'client_secret': config['client_secret']
        }
    
    def get_gateway_config(self) -> dict:
        """Gateway設定のみを取得"""
        config = self.get_all_config()
        return {
            'region': config['region'],
            'gateway_id': config['gateway_id']
        }


# グローバルインスタンス
test_config = TestConfig()


if __name__ == "__main__":
    """設定テスト用のメイン関数"""
    try:
        print("🔧 テスト設定を確認中...")
        config = test_config.get_all_config()
        
        print("\n📋 取得した設定:")
        print(f"   リージョン: {config['region']}")
        print(f"   User Pool ID: {config['user_pool_id']}")
        print(f"   Client ID: {config['client_id']}")
        print(f"   Client Secret: {config['client_secret'][:10]}...")
        print(f"   Gateway ID: {config['gateway_id']}")
        
        print("\n✅ 設定取得テスト完了")
        
    except Exception as e:
        print(f"\n❌ 設定取得テストエラー: {e}")
        import traceback
        traceback.print_exc()