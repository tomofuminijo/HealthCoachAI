"""
Healthmate-CoachAI CDK Stack

AWS CDK (Python) を使用してHealthmate-CoachAIサービスをデプロイするためのスタック
"""

from typing import Optional
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    Fn,
    Duration,
    RemovalPolicy,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_codebuild as codebuild,
    aws_logs as logs,
    aws_bedrockagentcore as agentcore,
)
from constructs import Construct


class CoachAICDKStack(Stack):
    """
    Healthmate-CoachAI サービス用のCDKスタック
    
    このスタックは以下のリソースを作成・管理します:
    - Amazon Bedrock AgentCore Agent
    - IAM Role とポリシー
    - ECR Repository
    - CodeBuild Project
    - CloudWatch Logs
    - AgentCore Memory
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 設定の取得
        self.config = self._load_configuration()
        
        # リソースの作成（段階的に実装）
        self.execution_role = self._create_execution_role()
        self.ecr_repository = self._create_ecr_repository()
        self.codebuild_project = self._create_codebuild_project()
        self.log_group = self._create_log_group()
        self.memory = self._create_memory()
        # TODO: ECRにイメージをプッシュしてからRuntimeを有効化
        # self.runtime = self._create_runtime()
        
        self._create_outputs()

    def _load_configuration(self) -> dict:
        """
        CDKコンテキストと環境変数から設定を読み込み
        
        Returns:
            設定辞書
        """
        config = {
            # 基本設定
            "agent_name": self.node.try_get_context("agent_name") or "healthmate-coach-ai",
            "health_manager_stack_name": self.node.try_get_context("health_manager_stack_name") or "Healthmate-HealthManagerStack",
            "log_level": self.node.try_get_context("log_level") or "INFO",
            "environment": self.node.try_get_context("environment") or "development",
            
            # エージェント設定
            "entrypoint": "healthmate_coach_ai/agent.py",
            "platform": "linux/arm64",
            "deployment_type": "container",
            
            # メモリ設定
            "memory_mode": "STM_ONLY",
            "memory_expiry_days": 30,
            
            # ECR設定
            "ecr_repository_name": "healthmate-coach-ai",
            "max_image_count": 10,
        }
        
        return config

    def _create_execution_role(self) -> iam.Role:
        """
        AgentCore Runtime用のIAMロールを作成
        
        Returns:
            作成されたIAMロール
        """
        # 信頼ポリシー（bedrock-agentcore.amazonaws.com サービスプリンシパル）
        trust_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")],
                    actions=["sts:AssumeRole"]
                )
            ]
        )
        
        # IAMロールを作成
        execution_role = iam.Role(
            self, "HealthmateCoachAIExecutionRole",
            role_name=f"Healthmate-CoachAI-AgentCore-Runtime-Role-CDK",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Healthmate-CoachAI AgentCore Runtime Role (CDK Managed)",
            max_session_duration=cdk.Duration.hours(1)
        )
        
        # AgentCore Runtime基本ポリシーを作成・アタッチ
        self._attach_runtime_policies(execution_role)
        
        return execution_role

    def _attach_runtime_policies(self, role: iam.Role) -> None:
        """
        AgentCore Runtime用のポリシーをロールにアタッチ
        
        Args:
            role: ポリシーをアタッチするIAMロール
        """
        # Bedrock権限
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:GetFoundationModel",
                "bedrock:ListFoundationModels"
            ],
            resources=["*"]
        )
        
        # AgentCore権限
        agentcore_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock-agentcore:*"],
            resources=["*"]
        )
        
        # CloudWatch Logs権限（作成されたログ群への書き込み権限を含む）
        logs_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams"
            ],
            resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock/agentcore/{self.config['agent_name']}*"
            ]
        )
        
        # ECR権限
        ecr_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage"
            ],
            resources=["*"]
        )
        
        # CloudFormation読み取り権限（設定取得用）
        cloudformation_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackResources"
            ],
            resources=[
                f"arn:aws:cloudformation:{self.region}:{self.account}:stack/{self.config['health_manager_stack_name']}/*"
            ]
        )
        
        # インラインポリシーとしてロールにアタッチ
        role.add_to_policy(bedrock_policy)
        role.add_to_policy(agentcore_policy)
        role.add_to_policy(logs_policy)
        role.add_to_policy(ecr_policy)
        role.add_to_policy(cloudformation_policy)

    def _create_ecr_repository(self) -> ecr.Repository:
        """
        ECRリポジトリを作成
        
        Returns:
            作成されたECRリポジトリ
        """
        repository = ecr.Repository(
            self, "HealthmateCoachAIRepository",
            repository_name=self.config["ecr_repository_name"],
            image_scan_on_push=True,  # セキュリティスキャンを有効化
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep only the latest 10 images",
                    max_image_count=self.config["max_image_count"],
                    rule_priority=1
                )
            ],
            removal_policy=RemovalPolicy.DESTROY  # 開発環境用
        )
        
        return repository

    def _create_codebuild_project(self) -> codebuild.Project:
        """
        CodeBuildプロジェクトを作成
        
        Returns:
            作成されたCodeBuildプロジェクト
        """
        # CodeBuild用のIAMロール
        codebuild_role = iam.Role(
            self, "HealthmateCoachAICodeBuildRole",
            role_name=f"Healthmate-CoachAI-CodeBuild-Role-CDK",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            description="Healthmate-CoachAI CodeBuild Role (CDK Managed)"
        )
        
        # CodeBuild権限を追加
        self._attach_codebuild_policies(codebuild_role)
        
        # CodeBuildプロジェクト
        project = codebuild.Project(
            self, "HealthmateCoachAIBuildProject",
            project_name=f"{self.config['agent_name']}-build",
            description="Healthmate-CoachAI Container Build Project",
            role=codebuild_role,
            
            # ビルド環境設定
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True  # Docker build用
            ),
            
            # ソース設定（GitHub統合を無効化、手動ビルド用）
            source=codebuild.Source.git_hub(
                owner="your-github-username",  # 実際のGitHubユーザー名に変更
                repo="healthmate-coach-ai",    # 実際のリポジトリ名に変更
                webhook=False  # Webhookを無効化
            ),
            
            # ビルドスペック
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Logging in to Amazon ECR...",
                            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Build started on `date`",
                            "echo Building the Docker image...",
                            f"docker build -t {self.config['ecr_repository_name']} .",
                            f"docker tag {self.config['ecr_repository_name']}:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/{self.config['ecr_repository_name']}:latest"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Build completed on `date`",
                            "echo Pushing the Docker image...",
                            f"docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/{self.config['ecr_repository_name']}:latest"
                        ]
                    }
                },
                "env": {
                    "variables": {
                        "AWS_DEFAULT_REGION": self.region,
                        "AWS_ACCOUNT_ID": self.account,
                        "IMAGE_REPO_NAME": self.config["ecr_repository_name"],
                        "IMAGE_TAG": "latest"
                    }
                }
            }),
            
            # タイムアウト設定
            timeout=Duration.minutes(30)
        )
        
        return project

    def _attach_codebuild_policies(self, role: iam.Role) -> None:
        """
        CodeBuild用のポリシーをロールにアタッチ
        
        Args:
            role: ポリシーをアタッチするIAMロール
        """
        # CloudWatch Logs権限
        logs_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/{self.config['agent_name']}-build*"
            ]
        )
        
        # ECR権限
        ecr_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:GetAuthorizationToken",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:PutImage"
            ],
            resources=["*"]
        )
        
        # S3権限（アーティファクト用）
        s3_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject"
            ],
            resources=["arn:aws:s3:::codepipeline-*"]
        )
        
        # インラインポリシーとしてロールにアタッチ
        role.add_to_policy(logs_policy)
        role.add_to_policy(ecr_policy)
        role.add_to_policy(s3_policy)

    def _create_log_group(self) -> logs.LogGroup:
        """
        CloudWatchログ統合を実装
        
        Returns:
            作成されたLogGroup
        """
        log_group = logs.LogGroup(
            self, "HealthmateCoachAILogGroup",
            log_group_name=f"/aws/bedrock/agentcore/{self.config['agent_name']}",
            retention=logs.RetentionDays.ONE_MONTH,  # 1ヶ月保持
            removal_policy=RemovalPolicy.DESTROY  # 開発環境用
        )
        
        return log_group

    def _create_memory(self) -> agentcore.CfnMemory:
        """
        AgentCore Memory を作成
        STM_ONLY モードでイベント有効期限を設定
        
        Returns:
            作成されたCfnMemory
        """
        memory = agentcore.CfnMemory(
            self, "HealthmateCoachAIMemory",
            name="healthmatecoachaimemory",  # ハイフンを削除してパターンに適合
            description="Healthmate-CoachAI AgentCore Memory for conversation history (STM_ONLY mode)",
            event_expiry_duration=self.config["memory_expiry_days"]  # 30日間のイベント有効期限
        )
        
        return memory

    def _get_cross_stack_configuration(self) -> dict:
        """
        HealthManagerスタックからクロススタック情報を取得
        
        Returns:
            クロススタック設定辞書
        """
        # HealthManagerスタックからGateway IDのみを取得
        # （Cognito情報はテストプログラムでのみ必要）
        gateway_id = Fn.import_value("Healthmate-HealthManager-GatewayId")
        
        return {
            "gateway_id": gateway_id,
        }

    def _build_environment_variables(self, cross_stack_config: dict) -> dict:
        """
        環境変数を動的に構築
        
        Args:
            cross_stack_config: クロススタック設定
            
        Returns:
            環境変数辞書
        """
        # AgentCore Runtime用の基本環境変数
        env_vars = {
            "HEALTHMANAGER_GATEWAY_ID": cross_stack_config["gateway_id"],
            "AWS_REGION": self.region,
            "HEALTH_STACK_NAME": self.config["health_manager_stack_name"],
            "LOG_LEVEL": self.config["log_level"],
            "AGENT_NAME": self.config["agent_name"],
            "AGENTCORE_MEMORY_ID": self.memory.attr_memory_id
        }
        
        # 環境固有の設定
        if self.config["environment"] == "development":
            env_vars["DEBUG"] = "true"
        
        return env_vars

    def _create_runtime(self) -> agentcore.CfnRuntime:
        """
        AgentCore Runtime を作成
        
        Returns:
            作成されたCfnRuntime
        """
        # クロススタック統合: HealthManagerスタックからの情報取得
        cross_stack_config = self._get_cross_stack_configuration()
        
        # 作成済みのECRリポジトリからイメージURIを取得
        image_uri = self.ecr_repository.repository_uri_for_tag("latest")
        
        # 環境変数の設定（クロススタック情報を含む）
        environment_variables = self._build_environment_variables(cross_stack_config)
        
        # CfnRuntime の作成（AWS CDK BedrockAgentCore API仕様に基づく）
        runtime = agentcore.CfnRuntime(
            self, "HealthmateCoachAIRuntime",
            agent_runtime_name="healthmatecoachairuntime",  # ハイフンを削除してパターンに適合
            description="Healthmate-CoachAI Agent Runtime",
            role_arn=self.execution_role.role_arn,
            
            # AgentRuntimeArtifact - コンテナ設定
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image_uri
                )
            ),
            
            # ネットワーク設定
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"  # サポートされている値: PUBLIC または VPC
            ),
            
            # 環境変数設定
            environment_variables=environment_variables
        )
        
        return runtime

    def _create_outputs(self) -> None:
        """
        スタック出力を作成
        
        他のサービスとの統合や運用監視に必要な情報を出力
        """
        # 基本情報の出力
        CfnOutput(
            self, "StackName",
            value=self.stack_name,
            description="CDK Stack Name"
        )
        
        CfnOutput(
            self, "Region",
            value=self.region,
            description="AWS Region"
        )
        
        CfnOutput(
            self, "Account",
            value=self.account,
            description="AWS Account ID"
        )
        
        # 設定情報の出力
        CfnOutput(
            self, "AgentName",
            value=self.config["agent_name"],
            description="Agent Name"
        )
        
        CfnOutput(
            self, "Environment",
            value=self.config["environment"],
            description="Environment (development/staging/production)"
        )
        
        # IAMロール情報の出力
        CfnOutput(
            self, "ExecutionRoleArn",
            value=self.execution_role.role_arn,
            description="AgentCore Execution Role ARN"
        )
        
        CfnOutput(
            self, "ExecutionRoleName",
            value=self.execution_role.role_name,
            description="AgentCore Execution Role Name"
        )
        
        # AgentCore Runtime情報の出力（ECRイメージ準備後に有効化）
        # CfnOutput(
        #     self, "RuntimeArn",
        #     value=self.runtime.attr_agent_runtime_arn,
        #     description="AgentCore Runtime ARN"
        # )
        
        # CfnOutput(
        #     self, "RuntimeId",
        #     value=self.runtime.attr_agent_runtime_id,
        #     description="AgentCore Runtime ID"
        # )
        
        # CfnOutput(
        #     self, "RuntimeName",
        #     value="healthmatecoachairuntime",
        #     description="AgentCore Runtime Name"
        # )
        
        # AgentCore Memory情報の出力
        CfnOutput(
            self, "MemoryArn",
            value=self.memory.attr_memory_arn,
            description="AgentCore Memory ARN"
        )
        
        CfnOutput(
            self, "MemoryId",
            value=self.memory.attr_memory_id,
            description="AgentCore Memory ID"
        )
        
        CfnOutput(
            self, "MemoryName",
            value="healthmatecoachaimemory",
            description="AgentCore Memory Name"
        )
        
        # ECRリポジトリ情報の出力
        CfnOutput(
            self, "ECRRepositoryUri",
            value=self.ecr_repository.repository_uri,
            description="ECR Repository URI"
        )
        
        CfnOutput(
            self, "ECRRepositoryName",
            value=self.ecr_repository.repository_name,
            description="ECR Repository Name"
        )
        
        # CodeBuildプロジェクト情報の出力
        CfnOutput(
            self, "CodeBuildProjectName",
            value=self.codebuild_project.project_name,
            description="CodeBuild Project Name"
        )
        
        CfnOutput(
            self, "CodeBuildProjectArn",
            value=self.codebuild_project.project_arn,
            description="CodeBuild Project ARN"
        )
        
        # CloudWatchログ情報の出力
        CfnOutput(
            self, "LogGroupName",
            value=self.log_group.log_group_name,
            description="CloudWatch Log Group Name"
        )
        
        CfnOutput(
            self, "LogGroupArn",
            value=self.log_group.log_group_arn,
            description="CloudWatch Log Group ARN"
        )