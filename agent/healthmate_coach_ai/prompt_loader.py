"""
システムプロンプトローダー

環境変数HEALTHMATE_ENVに基づいて適切なシステムプロンプトファイルを読み込みます。
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger('HealthCoachAI.PromptLoader')


class SystemPromptLoader:
    """システムプロンプトの読み込みと管理を行うクラス"""
    
    def __init__(self):
        self._prompt_cache: Dict[str, str] = {}
        self._prompts_dir = Path(__file__).parent / "prompts"
        
    def load_system_prompt(self, environment: str = None) -> str:
        """
        指定された環境のシステムプロンプトを読み込む
        
        Args:
            environment: 環境名 (dev, stage, prod)。Noneの場合は環境変数から取得
            
        Returns:
            システムプロンプトの文字列
            
        Raises:
            FileNotFoundError: プロンプトファイルが見つからない場合
            Exception: その他のエラー
        """
        if environment is None:
            environment = os.environ.get('HEALTHMATE_ENV', 'dev').lower()
        
        # キャッシュから取得を試行
        if environment in self._prompt_cache:
            logger.debug(f"システムプロンプトをキャッシュから取得: {environment}")
            return self._prompt_cache[environment]
        
        # ファイルから読み込み
        prompt_file = self._prompts_dir / f"coachai_system_prompt_{environment}.txt"
        
        if not prompt_file.exists():
            available_files = list(self._prompts_dir.glob("coachai_system_prompt_*.txt"))
            available_envs = [f.stem.replace("coachai_system_prompt_", "") for f in available_files]
            
            error_msg = (
                f"システムプロンプトファイルが見つかりません: {prompt_file}\n"
                f"利用可能な環境: {', '.join(available_envs)}"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_content = f.read().strip()
            
            # キャッシュに保存
            self._prompt_cache[environment] = prompt_content
            
            logger.info(f"システムプロンプトを読み込みました: {environment} ({len(prompt_content)}文字)")
            return prompt_content
            
        except Exception as e:
            error_msg = f"システムプロンプトファイルの読み込みエラー: {prompt_file} - {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def format_system_prompt(self, environment: str = None, **kwargs) -> str:
        """
        システムプロンプトを読み込み、動的変数を注入する
        
        Args:
            environment: 環境名
            **kwargs: プロンプト内の変数に注入する値
            
        Returns:
            フォーマット済みのシステムプロンプト
        """
        prompt_template = self.load_system_prompt(environment)
        
        try:
            formatted_prompt = prompt_template.format(**kwargs)
            logger.debug(f"システムプロンプトの変数注入完了: {len(kwargs)}個の変数")
            return formatted_prompt
            
        except KeyError as e:
            missing_var = str(e).strip("'")
            error_msg = f"システムプロンプトに必要な変数が不足しています: {missing_var}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        except Exception as e:
            error_msg = f"システムプロンプトのフォーマットエラー: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_available_environments(self) -> list:
        """利用可能な環境のリストを取得"""
        prompt_files = list(self._prompts_dir.glob("coachai_system_prompt_*.txt"))
        environments = [f.stem.replace("coachai_system_prompt_", "") for f in prompt_files]
        return sorted(environments)
    
    def clear_cache(self):
        """プロンプトキャッシュをクリア"""
        self._prompt_cache.clear()
        logger.debug("システムプロンプトキャッシュをクリアしました")


# グローバルインスタンス
_prompt_loader = SystemPromptLoader()


def load_system_prompt(environment: str = None) -> str:
    """
    システムプロンプトを読み込む（グローバル関数）
    
    Args:
        environment: 環境名
        
    Returns:
        システムプロンプトの文字列
    """
    return _prompt_loader.load_system_prompt(environment)


def format_system_prompt(environment: str = None, **kwargs) -> str:
    """
    システムプロンプトをフォーマットする（グローバル関数）
    
    Args:
        environment: 環境名
        **kwargs: プロンプト内の変数に注入する値
        
    Returns:
        フォーマット済みのシステムプロンプト
    """
    return _prompt_loader.format_system_prompt(environment, **kwargs)


def get_available_environments() -> list:
    """利用可能な環境のリストを取得（グローバル関数）"""
    return _prompt_loader.get_available_environments()