# FGI恐慌贪婪指数监控项目 - 通知发送模块
# 负责通过Telegram Bot API发送卖出提醒消息（支持多收件人）

import os
import requests

# 从环境变量读取Telegram配置
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")


def _parse_chat_ids(raw: str):
    """将环境变量中的 Chat ID 字符串解析为列表

    支持分隔符：逗号(,)、分号(;)、空白(空格/制表/换行)。
    例如：
      "123456, 5031618795" 或 "123456 5031618795" 或 每行一个ID

    返回：list[str]（保持为字符串，兼容群/频道负号ID）
    """
    if not raw:
        return []
    # 统一替换为空格，再按空白切分
    seps = [",", ";", "\n", "\r", "\t"]
    for s in seps:
        raw = raw.replace(s, " ")
    ids = [x.strip() for x in raw.split(" ") if x.strip()]
    return ids


def send_telegram(text):
    """发送消息到Telegram（支持多收件人）

    参数:
        text: 要发送的消息内容

    返回:
        list[dict] 或 None - 每个收件人的API响应字典；配置缺失时返回None
    """
    # 检查必要的环境变量是否配置
    if not TG_TOKEN or not TG_CHAT:
        print("Telegram not configured; printing message:\n", text)
        return None

    # 解析收件人列表
    chat_ids = _parse_chat_ids(TG_CHAT)
    if not chat_ids:
        print("No valid TELEGRAM_CHAT_ID provided; printing message:\n", text)
        return None

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    results = []
    last_error = None

    for cid in chat_ids:
        payload = {"chat_id": cid, "text": text}
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            results.append(r.json())
        except requests.exceptions.RequestException as e:
            # 不中断其它收件人，记录最后一次错误便于排查
            last_error = e
            print(f"Failed to send to chat_id={cid}: {e}")
            print(f"Message content: {text}")

    # 如果全部失败，抛出最后一个错误；否则返回成功/失败的混合结果
    if not results and last_error is not None:
        raise last_error
    return results
