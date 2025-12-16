# バックアップ・ロールバック計画

## 変更対象ファイルリスト

### 1. ディレクトリ構造
- `health_coach_ai/` → `healthmate_coach_ai/` (ディレクトリ名変更)
  - `health_coach_ai/__init__.py`
  - `health_coach_ai/agent.py`

### 2. 設定ファイル
- `create_custom_iam_role.py` (IAMロール名の変更)
- `deploy_to_aws.sh` (サービス名参照の更新)
- `destroy_from_aws.sh` (サービス名参照の更新)
- `.bedrock_agentcore.yaml` (存在する場合、エージェント名の更新)

### 3. ドキュメントファイル
- `README.md` (サービス名とパッケージ名の更新)
- `SETUP.md` (サービス名とパッケージ名の更新)

### 4. テストファイル
- `manual_test_agent.py` (パッケージ参照の更新)
- `manual_test_deployed_agent.py` (パッケージ参照の更新)
- `test_config_helper.py` (パッケージ参照の更新)
- `test_memory_integration.py` (パッケージ参照の更新)

### 5. ステアリングファイル
- `.kiro/steering/ai-agent.md` (サービス名参照の更新)

### 6. その他のファイル
- `check_deployment_status.py` (サービス名参照の確認・更新)

## バックアップ手順（Git使用）

### 1. 現在の作業状態の確認
```bash
# 現在のブランチとコミット状態を確認
git status
git log --oneline -5
```

### 2. 作業前のコミット作成
```bash
# 未コミットの変更があれば一時的にコミット
git add .
git commit -m "Pre-rename backup: Current HealthCoachAI state"
```

### 3. バックアップブランチの作成
```bash
# 現在の状態でバックアップブランチを作成
git checkout -b backup/healthcoach-ai-original
git push origin backup/healthcoach-ai-original

# メインブランチに戻る
git checkout main  # または現在の作業ブランチ
```

### 4. 作業用ブランチの作成
```bash
# 名前変更作業用の新しいブランチを作成
git checkout -b feature/rename-to-healthmate-coach-ai
```

## ロールバック手順（Git使用）

### 1. 作業の中断とブランチ切り替え
```bash
# 現在の作業を一時保存（必要に応じて）
git stash

# バックアップブランチに切り替え
git checkout backup/healthcoach-ai-original
```

### 2. 完全なロールバック（元の状態に復元）
```bash
# メインブランチを元の状態にリセット
git checkout main  # または元の作業ブランチ
git reset --hard backup/healthcoach-ai-original

# 強制プッシュ（注意：チーム開発の場合は事前に相談）
git push --force-with-lease origin main
```

### 3. AWSリソースのロールバック
```bash
# 新しいIAMロールが作成されている場合は削除
aws iam delete-role --role-name "Healthmate-CoachAI-AgentCore-Runtime-Role"

# 新しいAgentCoreエージェントが作成されている場合は削除
agentcore destroy --agent-name healthmate_coach_ai
```

### 4. 部分的なロールバック（特定のファイルのみ）
```bash
# 特定のファイルを元の状態に戻す
git checkout backup/healthcoach-ai-original -- create_custom_iam_role.py
git checkout backup/healthcoach-ai-original -- deploy_to_aws.sh
git checkout backup/healthcoach-ai-original -- README.md

# ディレクトリ全体を元に戻す
git checkout backup/healthcoach-ai-original -- health_coach_ai/
```

## 検証方法

### 1. Git状態の確認
```bash
# 現在のブランチとコミット状態
git branch -a
git log --oneline -5
git status
```

### 2. ファイル構造の確認
```bash
# ディレクトリ構造の確認
ls -la health_coach_ai/ 2>/dev/null || echo "health_coach_ai not found"
ls -la healthmate_coach_ai/ 2>/dev/null || echo "healthmate_coach_ai not found"
```

### 3. 設定ファイルの確認
```bash
# IAMロール名の確認
grep -n "ROLE_NAME" create_custom_iam_role.py

# デプロイスクリプトの確認
grep -n "HealthCoachAI\|health_coach_ai\|Healthmate-CoachAI\|healthmate_coach_ai" deploy_to_aws.sh
```

### 4. 動作確認
```bash
# Pythonインポートの確認
python -c "import healthmate_coach_ai" 2>/dev/null && echo "healthmate_coach_ai import OK" || echo "healthmate_coach_ai import failed"
python -c "import health_coach_ai" 2>/dev/null && echo "health_coach_ai import OK" || echo "health_coach_ai import failed"
```

### 5. バックアップブランチの確認
```bash
# バックアップブランチが存在することを確認
git show-branch backup/healthcoach-ai-original
```

## 緊急時の連絡先・手順

### 1. 問題発生時の対応
- 即座に作業を停止
- 現在の状態を記録
- ロールバック手順を実行

### 2. 復旧確認
- 元の機能が正常に動作することを確認
- AWSリソースが正常な状態であることを確認
- 他のサービスとの連携が正常であることを確認