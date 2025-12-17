#!/usr/bin/env python3
"""
Healthmate-CoachAI CDK Application

AWS CDK (Python) を使用してHealthmate-CoachAIサービスをデプロイするためのアプリケーション
"""

import aws_cdk as cdk
from coach_ai_cdk.coach_ai_stack import CoachAICDKStack


def main():
    """CDKアプリケーションのメインエントリーポイント"""
    app = cdk.App()

    # 環境設定
    env = cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-west-2"
    )

    # スタック名の設定（コンテキストから取得、デフォルトは固定値）
    stack_name = app.node.try_get_context("stack_name") or "Healthmate-CoachAI-Stack"

    # CoachAI CDKスタックを作成
    CoachAICDKStack(
        app, 
        stack_name,
        env=env,
        description="Healthmate-CoachAI Service CDK Stack - AgentCore Runtime Deployment"
    )

    app.synth()


if __name__ == "__main__":
    main()