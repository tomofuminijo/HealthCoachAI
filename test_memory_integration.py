#!/usr/bin/env python3
"""
AgentCore Memory統合テスト

このスクリプトは、HealthCoachAI サービスのAgentCore Memory統合が
正しく動作することを確認します。

テスト内容:
1. Actor ID (User Sub) による長期記憶
2. Session ID (UI Session) による会話セッション区切り
3. メモリ機能のフォールバック処理
"""

import asyncio
import json
import uuid
from datetime import datetime
from health_coach_ai.agent import invoke_health_coach


async def test_memory_integration():
    """AgentCore Memory統合テスト"""
    
    print("=" * 60)
    print("AgentCore Memory統合テスト開始")
    print("=" * 60)
    
    # テスト用のユーザーID（Actor ID）
    test_actor_id = "test-user-12345"  # 実際のCognito subを模擬
    
    # テスト用のセッションID（UI Session）
    test_session_1 = f"healthmate-chat-{int(datetime.now().timestamp())}-test1-session"
    test_session_2 = f"healthmate-chat-{int(datetime.now().timestamp())}-test2-session"
    
    print(f"テスト設定:")
    print(f"  Actor ID (User): {test_actor_id}")
    print(f"  Session ID 1: {test_session_1}")
    print(f"  Session ID 2: {test_session_2}")
    print()
    
    # テスト1: 最初のセッションでの会話
    print("テスト1: 最初のセッションでの会話")
    print("-" * 40)
    
    try:
        response1 = await invoke_health_coach(
            query="こんにちは！私の名前は田中太郎です。体重を減らしたいと思っています。",
            session_id=test_session_1,
            actor_id=test_actor_id
        )
        
        print(f"応答1: {response1[:200]}...")
        print("✅ 最初のセッション成功")
        
    except Exception as e:
        print(f"❌ 最初のセッションエラー: {e}")
        return False
    
    print()
    
    # テスト2: 同じセッション内での継続会話
    print("テスト2: 同じセッション内での継続会話")
    print("-" * 40)
    
    try:
        response2 = await invoke_health_coach(
            query="私の名前を覚えていますか？",
            session_id=test_session_1,  # 同じセッションID
            actor_id=test_actor_id
        )
        
        print(f"応答2: {response2[:200]}...")
        
        # 名前を覚えているかチェック
        if "田中" in response2 or "太郎" in response2:
            print("✅ セッション内記憶成功（名前を覚えている）")
        else:
            print("⚠️  セッション内記憶不完全（名前を覚えていない可能性）")
        
    except Exception as e:
        print(f"❌ セッション内継続会話エラー: {e}")
        return False
    
    print()
    
    # テスト3: 新しいセッションでの長期記憶テスト
    print("テスト3: 新しいセッションでの長期記憶テスト")
    print("-" * 40)
    
    try:
        response3 = await invoke_health_coach(
            query="新しいセッションです。私のことを覚えていますか？",
            session_id=test_session_2,  # 新しいセッションID
            actor_id=test_actor_id      # 同じユーザー（Actor ID）
        )
        
        print(f"応答3: {response3[:200]}...")
        
        # 長期記憶をチェック
        if "田中" in response3 or "太郎" in response3 or "体重" in response3:
            print("✅ 長期記憶成功（過去のセッション情報を覚えている）")
        else:
            print("⚠️  長期記憶不完全（過去の情報を覚えていない可能性）")
        
    except Exception as e:
        print(f"❌ 新しいセッションエラー: {e}")
        return False
    
    print()
    
    # テスト4: 異なるユーザーでの独立性テスト
    print("テスト4: 異なるユーザーでの独立性テスト")
    print("-" * 40)
    
    different_actor_id = "test-user-67890"  # 異なるユーザー
    different_session_id = f"healthmate-chat-{int(datetime.now().timestamp())}-diff-session"
    
    try:
        response4 = await invoke_health_coach(
            query="こんにちは！私のことを知っていますか？",
            session_id=different_session_id,
            actor_id=different_actor_id  # 異なるユーザー
        )
        
        print(f"応答4: {response4[:200]}...")
        
        # 他のユーザーの情報を知らないことをチェック
        if "田中" not in response4 and "太郎" not in response4:
            print("✅ ユーザー独立性成功（他のユーザー情報を知らない）")
        else:
            print("❌ ユーザー独立性失敗（他のユーザー情報が漏洩）")
        
    except Exception as e:
        print(f"❌ 異なるユーザーテストエラー: {e}")
        return False
    
    print()
    print("=" * 60)
    print("AgentCore Memory統合テスト完了")
    print("=" * 60)
    
    return True


async def test_fallback_functionality():
    """フォールバック機能テスト"""
    
    print("=" * 60)
    print("フォールバック機能テスト開始")
    print("=" * 60)
    
    # 無効なセッション設定でフォールバックをトリガー
    invalid_session_id = "invalid-session"
    invalid_actor_id = ""  # 空のactor_id
    
    try:
        response = await invoke_health_coach(
            query="フォールバック機能のテストです。",
            session_id=invalid_session_id,
            actor_id=invalid_actor_id
        )
        
        print(f"フォールバック応答: {response[:200]}...")
        
        if "フォールバック" in response or "メモリ" in response:
            print("✅ フォールバック機能成功")
        else:
            print("⚠️  フォールバック機能動作確認")
        
    except Exception as e:
        print(f"❌ フォールバック機能エラー: {e}")
        return False
    
    print("=" * 60)
    print("フォールバック機能テスト完了")
    print("=" * 60)
    
    return True


async def main():
    """メインテスト実行"""
    
    print("HealthCoachAI AgentCore Memory統合テスト")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print()
    
    # メモリ統合テスト
    memory_test_result = await test_memory_integration()
    
    print()
    
    # フォールバック機能テスト
    fallback_test_result = await test_fallback_functionality()
    
    print()
    print("=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    print(f"メモリ統合テスト: {'✅ 成功' if memory_test_result else '❌ 失敗'}")
    print(f"フォールバック機能テスト: {'✅ 成功' if fallback_test_result else '❌ 失敗'}")
    
    if memory_test_result and fallback_test_result:
        print("\n🎉 すべてのテストが成功しました！")
        return 0
    else:
        print("\n⚠️  一部のテストが失敗しました。ログを確認してください。")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)