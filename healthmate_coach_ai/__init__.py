"""
Healthmate-CoachAI - AI健康コーチエージェント

Amazon Bedrock AgentCore Runtime上で動作するPython + Strands Agentsベースの
健康支援AIエージェントです。
"""

__version__ = "0.1.0"

from .agent import app

__all__ = ["app"]