#!/bin/bash

# Healthmate-CoachAI エージェントのCloudWatchログを参照するスクリプト

set -e

# エージェント情報を取得
AGENT_ARN=$(agentcore status --output json | jq -r '.agents[] | select(.name=="healthmate_coach_ai") | .arn' 2>/dev/null || echo "")

if [ -z "$AGENT_ARN" ]; then
    echo "❌ エージェント情報を取得できませんでした"
    echo "   agentcore status を実行してエージェントが正常にデプロイされていることを確認してください"
    exit 1
fi

# ARNからエージェントIDを抽出
AGENT_ID=$(echo "$AGENT_ARN" | sed 's/.*runtime\///' | sed 's/\/.*$//')
LOG_GROUP="/aws/bedrock-agentcore/runtimes/${AGENT_ID}-DEFAULT"

echo "🔍 Healthmate-CoachAI エージェントログ参照"
echo "================================================================================"
echo "📋 エージェント情報:"
echo "   ARN: $AGENT_ARN"
echo "   ロググループ: $LOG_GROUP"
echo ""

# メニュー表示
echo "📋 ログ参照オプション:"
echo "   1. リアルタイムログ監視 (runtime-logs)"
echo "   2. リアルタイムログ監視 (otel-logs)"
echo "   3. 過去1時間のログ表示"
echo "   4. 過去30分のログ表示"
echo "   5. 過去10分のログ表示"
echo "   6. AWS Console でログを開く"
echo "   7. GenAI Observability Dashboard を開く"
echo ""

read -p "選択してください (1-7): " choice

case $choice in
    1)
        echo "🔄 リアルタイムログ監視を開始します (runtime-logs)..."
        echo "   Ctrl+C で停止できます"
        echo ""
        aws logs tail "$LOG_GROUP" \
            --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" \
            --follow
        ;;
    2)
        echo "🔄 リアルタイムログ監視を開始します (otel-logs)..."
        echo "   Ctrl+C で停止できます"
        echo ""
        aws logs tail "$LOG_GROUP" \
            --log-stream-names "otel-rt-logs" \
            --follow
        ;;
    3)
        echo "📋 過去1時間のログを表示します..."
        echo ""
        aws logs tail "$LOG_GROUP" \
            --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" \
            --since 1h
        ;;
    4)
        echo "📋 過去30分のログを表示します..."
        echo ""
        aws logs tail "$LOG_GROUP" \
            --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" \
            --since 30m
        ;;
    5)
        echo "📋 過去10分のログを表示します..."
        echo ""
        aws logs tail "$LOG_GROUP" \
            --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" \
            --since 10m
        ;;
    6)
        # URLエンコードされたロググループ名
        ENCODED_LOG_GROUP=$(echo "$LOG_GROUP" | sed 's/\//%2F/g')
        CONSOLE_URL="https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logsV2:log-groups/log-group/${ENCODED_LOG_GROUP}"
        echo "🌐 AWS Console でログを開きます..."
        echo "   URL: $CONSOLE_URL"
        open "$CONSOLE_URL" 2>/dev/null || echo "   ブラウザで上記URLを開いてください"
        ;;
    7)
        DASHBOARD_URL="https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#gen-ai-observability/agent-core"
        echo "🌐 GenAI Observability Dashboard を開きます..."
        echo "   URL: $DASHBOARD_URL"
        open "$DASHBOARD_URL" 2>/dev/null || echo "   ブラウザで上記URLを開いてください"
        ;;
    *)
        echo "❌ 無効な選択です"
        exit 1
        ;;
esac