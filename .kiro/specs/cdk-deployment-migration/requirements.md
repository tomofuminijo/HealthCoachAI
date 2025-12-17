# 要件定義書

## 概要

Healthmate-CoachAI サービスのデプロイメント方式を、現在の `agentcore launch` コマンドベースから AWS CDK (Python) ベースのInfrastructure as Code (IaC) アプローチに移行します。これにより、デプロイメントの再現性、バージョン管理、および他のHealthmateサービスとの統合を向上させます。

## 用語集

- **CDK_Stack**: AWS CDK (Python) で定義されるインフラストラクチャスタック
- **AgentCore_Runtime**: Amazon Bedrock AgentCore Runtime の実行環境
- **Container_Deployment**: コンテナベースのデプロイメント方式
- **IAM_Role**: AWS Identity and Access Management ロール
- **ECR_Repository**: Amazon Elastic Container Registry リポジトリ
- **CodeBuild_Project**: AWS CodeBuild プロジェクト
- **Gateway_Integration**: AgentCore Gateway との統合設定
- **Environment_Variables**: エージェント実行時の環境変数設定

## 要件

### 要件 1

**ユーザーストーリー:** 開発者として、CDKを使用してHealthmate-CoachAIをデプロイしたい。そうすることで、インフラストラクチャをコードとして管理し、バージョン管理できる。

#### 受け入れ基準

1. CDKスタックが作成されるとき、CDK_Stackは必要なすべてのAWSリソースを定義する
2. CDKデプロイが実行されるとき、CDK_Stackは AgentCore_Runtime、IAM_Role、ECR_Repository、CodeBuild_Project を作成する
3. インフラストラクチャが変更されるとき、CDK_Stackは変更をバージョン管理システムで追跡可能にする
4. CDKスタックがデプロイされるとき、CDK_Stackは既存の手動作成リソースと競合しない
5. CDKによるリソース作成が完了するとき、CDK_Stackは作成されたリソースの情報を出力する

### 要件 2

**ユーザーストーリー:** システム管理者として、CDKで作成されたエージェントが既存のHealthManagerMCPサービスと統合してほしい。そうすることで、サービス間の連携を維持できる。

#### 受け入れ基準

1. CDKスタックがデプロイされるとき、CDK_Stackは既存のHealthManagerスタックからGateway_Integration情報を取得する
2. エージェントが起動するとき、AgentCore_Runtimeは適切なEnvironment_Variablesを使用してHealthManagerMCPに接続する
3. Gateway統合が設定されるとき、CDK_Stackは必要な認証情報とエンドポイント情報を自動設定する
4. 外部依存関係が変更されるとき、CDK_Stackは設定を動的に更新する
5. サービス間通信が確立されるとき、AgentCore_Runtimeは既存のMCPプロトコルを使用して通信する

### 要件 3

**ユーザーストーリー:** 開発者として、CDKデプロイメントが現在のagentcore launchと同等の機能を提供してほしい。そうすることで、既存の機能を失うことなく移行できる。

#### 受け入れ基準

1. CDKデプロイが実行されるとき、CDK_Stackは現在のagentcore launch設定と同等のContainer_Deploymentを作成する
2. エージェントが実行されるとき、AgentCore_Runtimeは現在と同じentrypointとplatform設定を使用する
3. IAMロールが作成されるとき、CDK_Stackは現在のカスタムIAMロールと同等の権限を付与する
4. ECRリポジトリが管理されるとき、CDK_Stackは自動的にリポジトリを作成し管理する
5. 環境変数が設定されるとき、CDK_Stackは現在のHEALTHMANAGER_GATEWAY_IDとAWS_REGIONを適切に設定する

### 要件 4

**ユーザーストーリー:** 開発者として、CDKスタックが適切なエラーハンドリングとロールバック機能を提供してほしい。そうすることで、デプロイメント失敗時に安全に復旧できる。

#### 受け入れ基準

1. CDKデプロイが失敗するとき、CDK_Stackは自動的にロールバックを実行する
2. リソース作成エラーが発生するとき、CDK_Stackは詳細なエラー情報を提供する
3. 依存関係の問題が検出されるとき、CDK_Stackは適切なエラーメッセージを表示する
4. 権限不足が発生するとき、CDK_Stackは必要な権限を明確に示す
5. 部分的なデプロイ失敗が起こるとき、CDK_Stackは作成済みリソースを適切にクリーンアップする

### 要件 5

**ユーザーストーリー:** 開発者として、CDKスタックが設定可能で環境に応じてカスタマイズできてほしい。そうすることで、開発・ステージング・本番環境で適切に使い分けできる。

#### 受け入れ基準

1. 環境設定が提供されるとき、CDK_Stackは環境変数またはコンテキスト値を使用して設定を調整する
2. リージョンが指定されるとき、CDK_Stackは指定されたリージョンにリソースを作成する
3. スタック名が設定されるとき、CDK_Stackはカスタムスタック名を使用してリソースを作成する
4. 依存スタック名が変更されるとき、CDK_Stackは適切な依存関係を解決する
5. デバッグモードが有効化されるとき、CDK_Stackは詳細なログ出力を提供する

### 要件 6

**ユーザーストーリー:** 開発者として、CDKデプロイメントが既存のテストとモニタリング機能を維持してほしい。そうすることで、デプロイ後の検証と運用監視を継続できる。

#### 受け入れ基準

1. CDKデプロイが完了するとき、CDK_Stackは既存のテストスクリプトが使用可能な状態を維持する
2. エージェントステータス確認が要求されるとき、AgentCore_Runtimeは現在のagentcore statusコマンドと同等の情報を提供する
3. ログ出力が設定されるとき、CDK_Stackは適切なCloudWatchログ統合を提供する
4. メトリクス収集が有効化されるとき、AgentCore_Runtimeは運用監視に必要なメトリクスを出力する
5. デプロイ検証が実行されるとき、CDK_Stackは自動的にヘルスチェックを実行する

### 要件 7

**ユーザーストーリー:** 開発者として、CDKスタックが既存のagentcore launchワークフローからの移行パスを提供してほしい。そうすることで、段階的に移行できる。

#### 受け入れ基準

1. 移行スクリプトが実行されるとき、CDK_Stackは既存の.bedrock_agentcore.yaml設定を読み取り変換する
2. 既存リソースが検出されるとき、CDK_Stackは既存リソースをインポートまたは置き換えオプションを提供する
3. 移行プロセスが開始されるとき、CDK_Stackは現在のデプロイメント状態をバックアップする
4. 移行が完了するとき、CDK_Stackは古いagentcore launch設定の無効化を推奨する
5. ロールバックが必要なとき、CDK_Stackは以前のagentcore launch設定への復帰方法を提供する