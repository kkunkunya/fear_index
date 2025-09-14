# FGI恐慌贪婪指数监控项目 - 通知发送模块
# 负责通过Telegram Bot API发送卖出提醒消息

import os
import requests

# 从环境变量读取Telegram配置
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(text):
    """
    发送消息到Telegram

    参数:
        text: 要发送的消息内容

    返回:
        dict - Telegram API响应，如果配置不完整则返回None
    """
    # 检查必要的环境变量是否配置
    if not TG_TOKEN or not TG_CHAT:
        print("Telegram not configured; printing message:\n", text)
        return None

    # 构造Telegram Bot API URL
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    # 构造请求载荷
    payload = {"chat_id": TG_CHAT, "text": text}

    try:
        # 发送HTTP POST请求到Telegram API
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()  # 如果HTTP状态码表示错误，抛出异常
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")
        print(f"Message content: {text}")
        raise
