# FGI恐慌贪婪指数监控项目 - 状态管理模块
# 负责处理JSON状态文件的读写、冷却期检查、日期处理等功能

import json
import os
import datetime as dt

# 状态文件配置
STATE_DIR = "state"
STATE_FILE = os.path.join(STATE_DIR, "state.json")
DATE_FMT = "%Y-%m-%d"

# 默认状态结构
DEFAULT_STATE = {
    "last_processed_date": None,  # 上次处理的FGI自然日
    "last_trigger_at": {"70": None, "80": None, "90": None},  # 各阈值最后触发日期
    "bootstrapped": False,  # 是否已完成首次初始化
}


def load_state():
    """
    加载JSON状态文件，实现状态持久化

    如果状态文件不存在，将自动创建包含默认结构的新文件
    这确保了项目首次运行时能正常初始化

    返回:
        dict: 包含以下键的状态字典
            - last_processed_date: 最后处理的FGI数据日期，避免重复处理
            - last_trigger_at: 各阈值(70/80/90)的最后触发时间，用于冷却计算
            - bootstrapped: 是否完成首次初始化，控制历史信号抑制
    """
    if not os.path.exists(STATE_FILE):
        os.makedirs(STATE_DIR, exist_ok=True)
        save_state(DEFAULT_STATE.copy())
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    """保存状态到JSON文件"""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def days_since(date_str, today):
    """计算从指定日期到今天的天数差"""
    if not date_str:
        return None
    d = dt.datetime.strptime(date_str, DATE_FMT).date()
    return (today - d).days


def today_utc_date():
    """获取当前UTC日期"""
    return dt.datetime.utcnow().date()


def in_cooldown(state, level, today):
    """
    检查指定阈值是否在冷却期内

    冷却机制设计：每个阈值(70/80/90)独立维护7天冷却期
    这避免了短期内同一阈值的重复通知，减少噪音

    参数:
        state: 当前状态字典
        level: 要检查的阈值 (70, 80, 或 90)
        today: 当前日期 (date对象)

    返回:
        bool: True表示在冷却期内，False表示可以触发
    """
    last = state["last_trigger_at"].get(str(level))
    if not last:
        return False  # 从未触发过，不在冷却期
    since = days_since(last, today)
    return since is not None and since < 7  # 7天内为冷却期


def mark_trigger(state, level, today):
    """标记指定阈值的触发时间"""
    state["last_trigger_at"][str(level)] = today.strftime(DATE_FMT)


def mark_processed(state, date_obj):
    """标记已处理的日期"""
    state["last_processed_date"] = date_obj.strftime(DATE_FMT)


def bootstrapped(state):
    """检查是否已完成首次初始化"""
    return state.get("bootstrapped", False)


def set_bootstrapped(state):
    """标记已完成首次初始化"""
    state["bootstrapped"] = True
