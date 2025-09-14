#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram连接测试脚本
用于验证Bot Token和Chat ID是否正确配置
"""

import os
import requests

def test_telegram_connection():
    """测试Telegram Bot连接"""

    # 从环境变量获取配置（在GitHub Actions中使用）
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    # 如果环境变量不存在，使用硬编码值进行本地测试
    if not bot_token:
        bot_token = "8420792636:AAH9bRcdzzt24huBYHs8lXGkC3TUiye-33Y"
    if not chat_id:
        chat_id = "5468993947"

    print(f"🤖 测试Telegram Bot连接...")
    print(f"Bot Token: {bot_token[:20]}...")
    print(f"Chat ID: {chat_id}")

    # 1. 测试Bot是否有效
    try:
        bot_info_url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(bot_info_url, timeout=10)
        response.raise_for_status()

        bot_info = response.json()
        if bot_info['ok']:
            print(f"✅ Bot验证成功: {bot_info['result']['first_name']} (@{bot_info['result']['username']})")
        else:
            print(f"❌ Bot验证失败: {bot_info}")
            return False

    except Exception as e:
        print(f"❌ Bot连接失败: {e}")
        return False

    # 2. 测试发送消息
    try:
        message = "🧪 FGI监控系统连接测试\n\n这是一条测试消息，用于验证Telegram Bot配置是否正确。\n\n如果你收到这条消息，说明连接正常！"

        send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }

        response = requests.post(send_url, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        if result['ok']:
            print(f"✅ 测试消息发送成功!")
            print(f"📩 Message ID: {result['result']['message_id']}")
            return True
        else:
            print(f"❌ 消息发送失败: {result}")
            return False

    except Exception as e:
        print(f"❌ 消息发送异常: {e}")
        return False

if __name__ == "__main__":
    success = test_telegram_connection()
    if success:
        print("\n🎉 Telegram连接测试通过!")
    else:
        print("\n❌ Telegram连接测试失败，请检查配置!")
        exit(1)