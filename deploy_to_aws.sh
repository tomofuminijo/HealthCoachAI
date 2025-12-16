#!/bin/bash

# Healthmate-CoachAI エージェントをAWSにデプロイするスクリプト
# カスタムIAMロールを使用したベストプラクティス版

set -e  # エラー時に停止

echo "🚀 Healthmate-CoachAI エージェントをAWSにデプロイします"
echo "=" * 80

# AWS設定
export AWS_DEFAULT_REGION=${AWS_REGION:-us-west-2}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
ROLE_NAME="Healthmate-CoachAI-AgentCore-Runtime-Role"
CUSTOM_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo "🔐 AWS設定を確認中..."
echo "📍 リージョン: $AWS_DEFAULT_REGION"
echo "🏢 アカウントID: $ACCOUNT_ID"
echo "🎭 カスタムロール: $CUSTOM_ROLE_ARN"

# AWS認証情報の確認
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ AWS認証情報が設定されていません。"
    echo "   以下のいずれかの方法でAWS認証を設定してください:"
    echo "   1. aws configure"
    echo "   2. 環境変数 (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
    echo "   3. IAMロール (EC2/Lambda等)"
    exit 1
fi

echo "✅ AWS認証情報確認完了"

# カスタムIAMロールの存在確認
echo ""
echo "🔍 カスタムIAMロールの存在を確認中..."
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "✅ カスタムIAMロール '$ROLE_NAME' が存在します"
else
    echo "❌ カスタムIAMロール '$ROLE_NAME' が見つかりません"
    echo ""
    echo "🛠️  カスタムIAMロールを作成しますか？ (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "🔧 カスタムIAMロールを作成中..."
        python3 create_custom_iam_role.py
        if [ $? -ne 0 ]; then
            echo "❌ カスタムIAMロール作成に失敗しました"
            exit 1
        fi
        echo "✅ カスタムIAMロール作成完了"
    else
        echo "❌ カスタムIAMロールが必要です。以下のコマンドで作成してください:"
        echo "   python3 create_custom_iam_role.py"
        exit 1
    fi
fi

# 仮想環境をアクティベート（存在する場合）
if [ -d "venv" ]; then
    echo ""
    echo "🐍 仮想環境をアクティベート中..."
    source venv/bin/activate
    echo "✅ 仮想環境アクティベート完了"
fi

echo ""
echo "📦 依存関係を確認中..."
pip install -q --upgrade bedrock-agentcore strands-agents

echo ""
echo "🔧 AgentCore設定を更新中..."
echo "   カスタムIAMロールを使用: $CUSTOM_ROLE_ARN"

# CloudFormationからGateway IDを取得
echo ""
echo "🔍 Healthmate-HealthManagerスタックからGateway IDを取得中..."
STACK_NAME="Healthmate-HealthManagerStack"
GATEWAY_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`GatewayId`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$GATEWAY_ID" ] || [ "$GATEWAY_ID" = "None" ]; then
    echo "❌ CloudFormationスタック '$STACK_NAME' からGateway IDを取得できませんでした"
    echo "   スタックが存在し、GatewayId出力があることを確認してください"
    exit 1
fi

echo "✅ Gateway ID取得成功: $GATEWAY_ID"

# AgentCore設定でカスタムロールを指定
agentcore configure \
    --entrypoint healthmate_coach_ai/agent.py \
    --name healthmate_coach_ai \
    --execution-role "$CUSTOM_ROLE_ARN" \
    --deployment-type container \
    --ecr auto \
    --non-interactive

echo ""
echo "🔍 更新された設定を確認中..."
cat .bedrock_agentcore.yaml

echo ""
echo "🚀 AgentCore デプロイを開始します..."
echo "   エージェント名: healthmate_coach_ai"
echo "   エントリーポイント: healthmate_coach_ai/agent.py"
echo "   カスタムIAMロール: $CUSTOM_ROLE_ARN"
echo ""

# AgentCore デプロイを実行（環境変数付き）
agentcore launch \
    --env HEALTHMANAGER_GATEWAY_ID="$GATEWAY_ID" \
    --env AWS_REGION="$AWS_DEFAULT_REGION"

echo ""
echo "✅ デプロイが完了しました！"
echo ""
echo "📋 デプロイ情報:"
echo "   🎭 使用したIAMロール: $CUSTOM_ROLE_ARN"
echo "   📍 リージョン: $AWS_DEFAULT_REGION"
echo "   🏢 アカウント: $ACCOUNT_ID"
echo ""
echo "🔐 IAMロールに含まれる権限:"
echo "   ✅ AgentCore Runtime基本権限"
echo "   ✅ CloudFormation読み取り権限"
echo "   ✅ Cognito読み取り権限"
echo ""
echo "📋 次のステップ:"
echo "   1. agentcore status でエージェント状態を確認"
echo "   2. manual_test_deployed_agent.py でテスト実行"
echo "   3. HealthMate UI からエージェントを呼び出し"
echo ""
echo "🧪 テスト実行コマンド:"
echo "   python3 manual_test_deployed_agent.py"
echo ""