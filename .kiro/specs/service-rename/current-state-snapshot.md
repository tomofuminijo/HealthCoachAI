# 現在のサービス状態スナップショット

## 作成日時
2024年12月16日

## ディレクトリ構造
```
HealthCoachAI/
├── health_coach_ai/
│   ├── __init__.py
│   └── agent.py
├── .kiro/
│   ├── specs/
│   └── steering/
│       └── ai-agent.md
├── create_custom_iam_role.py
├── deploy_to_aws.sh
├── destroy_from_aws.sh
├── README.md
├── SETUP.md
├── manual_test_agent.py
├── manual_test_deployed_agent.py
├── test_config_helper.py
├── test_memory_integration.py
├── check_deployment_status.py
├── requirements.txt
├── agentcore-trust-policy.json
├── bedrock-agentcore-runtime-policy.json
├── .dockerignore
└── .gitignore
```

## 主要設定値

### IAMロール名
- 現在: `HealthCoachAI-AgentCore-Runtime-Role`
- 変更後: `Healthmate-CoachAI-AgentCore-Runtime-Role`

### Pythonパッケージ名
- 現在: `health_coach_ai`
- 変更後: `healthmate_coach_ai`

### AgentCoreエージェント名
- 現在: `health_coach_ai`
- 変更後: `healthmate_coach_ai`

### サービス名
- 現在: `HealthCoachAI`
- 変更後: `Healthmate-CoachAI`

## 主要ファイルの内容確認

### create_custom_iam_role.py
- ロール名: `HealthCoachAI-AgentCore-Runtime-Role`
- ポリシー名: `HealthCoachAI-AgentCore-Runtime-Policy`

### deploy_to_aws.sh
- ロール名: `HealthCoachAI-AgentCore-Runtime-Role`
- エントリーポイント: `health_coach_ai/agent.py`
- エージェント名: `health_coach_ai`

### health_coach_ai/__init__.py
- パッケージ名: `health_coach_ai`
- バージョン: `0.1.0`

### health_coach_ai/agent.py
- メモリID: `health_coach_ai_mem-yxqD6w75pO`
- 各種コメントとログメッセージに `HealthCoachAI` が含まれる

## 変更が必要なファイル一覧

### 1. ディレクトリ名変更
- `health_coach_ai/` → `healthmate_coach_ai/`

### 2. 設定ファイル
- `create_custom_iam_role.py`
- `deploy_to_aws.sh`
- `destroy_from_aws.sh`

### 3. ドキュメント
- `README.md`
- `SETUP.md`

### 4. テストファイル
- `manual_test_agent.py`
- `manual_test_deployed_agent.py`
- `test_config_helper.py`
- `test_memory_integration.py`

### 5. ステアリングファイル
- `.kiro/steering/ai-agent.md`

### 6. その他
- `check_deployment_status.py`

## 現在のAWSリソース状態
（実際のデプロイ状況は実行時に確認が必要）

## バックアップ作成完了
このスナップショットファイルと backup-plan.md により、現在の状態が記録されました。