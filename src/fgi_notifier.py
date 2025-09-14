# FGI恐慌贪婪指数监控项目 - 主逻辑模块
# 整合所有功能模块，实现完整的监控和通知流程

import os
import sys
import requests
import datetime as dt
import asyncio
from statistics import mean

# 导入项目内部模块
from src.config import (
    FGI_API,
    THRESHOLDS,
    SELL_MAP,
    COOLDOWN_DAYS,
    BOOTSTRAP_SUPPRESS_FIRST_DAY,
    ENABLE_DAILY_REPORT,
    VERBOSE_MODE,
    REPORT_THRESHOLD_DISTANCE,
)
from src.state import (
    load_state,
    save_state,
    today_utc_date,
    in_cooldown,
    mark_trigger,
    mark_processed,
    bootstrapped,
    set_bootstrapped,
    days_since,  # 添加缺失的导入
)
from src.notify import send_telegram
from src.strategy import compute_fgi7, two_consecutive_ge, crossings

# 避免循环导入，动态导入 bot_handler 和 scheduled_reports_handler
def get_bot_handler():
    from src.bot_handler import bot_handler
    return bot_handler

def get_scheduled_reports_handler():
    from src.scheduled_reports import scheduled_reports_handler
    return scheduled_reports_handler


def fetch_fgi():
    """
    从alternative.me获取并处理FGI数据

    返回:
        list - [(date, value)] 按日期升序排列的FGI数据列表
    """
    r = requests.get(FGI_API, timeout=20)
    r.raise_for_status()
    data = r.json()["data"]

    # API返回常见为倒序；统一为按日期升序
    items = []
    for d in data:
        ts = int(d["timestamp"])
        day = dt.datetime.utcfromtimestamp(ts).date()
        val = int(d["value"])
        items.append((day, val))

    items.sort(key=lambda x: x[0])

    # 去重: 同日多条保留最后一条（理论不会发生）
    dedup = {}
    for day, val in items:
        dedup[day] = val

    out = sorted(dedup.items(), key=lambda x: x[0])  # [(date, val)]
    return out


def main(mode="monitor"):
    """
    主逻辑函数 - 执行完整的FGI监控流程

    参数:
        mode (str): 运行模式
            - "monitor": 监控模式（默认）- 触发检测 + 被动汇报
            - "bot": Bot命令模式 - 启动Telegram Bot监听命令
            - "scheduled": 定时汇报模式 - 发送早中晚定时汇报
            - "test": 测试模式 - 强制运行，忽略日期检查

    业务流程说明:
    1. 状态管理：加载持久化状态，支持断点续传
    2. 数据获取：从alternative.me API获取最新FGI数据
    3. 数据验证：确保有足够历史数据进行计算
    4. Bootstrap处理：首次运行时避免触发历史信号
    5. 增量处理：仅处理未处理过的新日期数据
    6. 策略计算：FGI7计算、上穿检测、连续天数检测
    7. 冷却过滤：应用7天独立冷却期机制
    8. 消息生成：格式化卖出提醒消息
    9. 通知发送：通过Telegram发送告警
    10. 状态更新：持久化最新状态信息

    返回:
        int - 程序退出码
            0: 成功执行
            1: 数据获取失败
            2: Bot模式初始化失败
    """
    # 运行模式处理
    if mode == "bot":
        return run_bot_mode()
    elif mode == "scheduled":
        return run_scheduled_mode()
    elif mode != "monitor" and mode != "test":
        print(f"Unknown mode: {mode}. Available modes: monitor, bot, scheduled, test")
        return 1

    # 监控模式 (默认) 和 测试模式
    # 测试模式会强制运行，忽略日期检查
    # 1. 加载状态
    state = load_state()

    # 2. 获取FGI数据
    try:
        values = fetch_fgi()
    except Exception as e:
        print(f"Failed to fetch FGI data: {e}")
        return 1

    if len(values) < 8:
        print("Insufficient FGI history; need >= 8 days.")
        return 0

    # 3. 今日自然日（按FGI数据最后一天）
    latest_day, latest_val = values[-1]
    prev7, today7 = compute_fgi7(values)

    if prev7 is None:
        print("Not enough data for FGI7.")
        return 0

    # 4. 首次上线：记录状态，不触发历史信号
    if BOOTSTRAP_SUPPRESS_FIRST_DAY and not bootstrapped(state):
        set_bootstrapped(state)
        mark_processed(state, latest_day)
        save_state(state)
        send_telegram(
            f"[初始化] 已上线并开始跟踪 FGI\n最近日期: {latest_day} FGI={latest_val} FGI7={today7}"
        )
        print("Bootstrapped. No historical firing.")
        return 0

    # 5. 无新日数据则跳过（测试模式除外）
    if mode != "test":
        last_proc = state.get("last_processed_date")
        if last_proc:
            last_proc_date = dt.datetime.strptime(last_proc, "%Y-%m-%d").date()
            if latest_day <= last_proc_date:
                print(f"No new day. latest={latest_day}, last_processed={last_proc_date}")
                return 0
    else:
        print(f"[测试模式] 忽略日期检查，强制执行处理逻辑")

    # 6. 核心策略判定
    fired_levels = []

    # 6.1) 上穿判定（70->80->90顺序，允许同日多级）
    ups = crossings(prev7, today7, THRESHOLDS)
    fired_levels.extend(ups)

    # 6.2) 连续两日 >=90 的 90桶判定（若未因上穿已触发）
    if 90 not in ups and two_consecutive_ge(values, 90):
        fired_levels.append(90)

    # 6.3) 低于60不卖：非硬条件，仅提示；不会清除已触发层的冷却
    below_60_note = today7 < 60

    # 7. 冷却过滤
    today = latest_day
    final_levels = []
    for t in fired_levels:
        if not in_cooldown(state, t, today):
            final_levels.append(t)

    # 8. 组装消息
    lines = []
    lines.append("[卖出提醒] FGI7触发")
    lines.append(f"日期: {today} (UTC)")
    lines.append(f"今日FGI7: {today7} (昨日: {prev7})，今日FGI: {latest_val}")

    if final_levels:
        actions = []
        for t in final_levels:
            pct = SELL_MAP[t]
            actions.append(f"上穿{t} → 卖出{pct}%")
        lines.append("触发: " + "；".join(actions))
    else:
        if fired_levels:
            lines.append("触发: 有信号但处于冷却期，未提醒新卖出")
        else:
            lines.append("触发: 无")

    if today7 < 60:
        lines.append("说明: FGI7<60（不卖，仅提示）")

    lines.append("规则: 同一阈值7天内只执行一次；跨级同日依序触发")
    lines.append("数据源: alternative.me")

    message = "\n".join(lines)

    # 9. 发送通知和汇报
    if final_levels:
        # 有触发时发送卖出提醒
        try:
            send_telegram(message)
            for t in final_levels:
                mark_trigger(state, t, today)
            if VERBOSE_MODE:
                print(f"Sent trigger notification for levels: {final_levels}")
        except Exception as e:
            print(f"Failed to send notification: {e}")
            # 不返回错误，继续处理状态更新
    else:
        print("No final actions to notify.")

    # 9.1 每日汇报功能（即使无触发也汇报）
    if ENABLE_DAILY_REPORT:
        try:
            report_message = generate_daily_report(
                today, latest_val, prev7, today7, fired_levels, final_levels, state
            )
            if report_message:
                send_telegram(report_message)
                if VERBOSE_MODE:
                    print("Sent daily report")
        except Exception as e:
            print(f"Failed to send daily report: {e}")

    # 9.2 详细模式日志输出
    if VERBOSE_MODE:
        print(f"Verbose info:")
        print(f"  - Data points: {len(values)}")
        print(f"  - FGI7 trend: {prev7:.2f} → {today7:.2f} ({today7-prev7:+.2f})")
        print(f"  - Fired levels: {fired_levels}")
        print(f"  - Final levels: {final_levels}")
        print(f"  - Cooldown status: {get_cooldown_status(state)}")

    # 10. 更新处理标记与持久化
    mark_processed(state, today)
    save_state(state)
    print("Done.")
    return 0


def generate_daily_report(today, latest_val, prev7, today7, fired_levels, final_levels, state):
    """生成每日数据汇报消息"""

    # 如果有最终触发，不重复发送汇报（已经有卖出提醒了）
    if final_levels:
        return None

    # 判断是否需要发送汇报
    should_report = False

    # 条件1：接近阈值时汇报
    for threshold in THRESHOLDS:
        distance = threshold - today7
        if 0 < distance <= REPORT_THRESHOLD_DISTANCE:
            should_report = True
            break

    # 条件2：有触发但被冷却时汇报
    if fired_levels and not final_levels:
        should_report = True

    # 条件3：FGI7变化较大时汇报（变化超过5）
    if abs(today7 - prev7) >= 5:
        should_report = True

    # 条件4：每周汇报一次状态（周日汇报）
    if dt.datetime.now().weekday() == 6:  # 周日
        should_report = True

    if not should_report:
        return None

    # 生成汇报消息
    lines = []
    lines.append("📊 FGI监控系统状态汇报")
    lines.append(f"日期: {today} (UTC)")
    lines.append(f"今日FGI: {latest_val}")
    lines.append(f"FGI7: {today7:.2f} (昨日: {prev7:.2f})")

    # 趋势分析
    change = today7 - prev7
    if change > 0:
        trend = f"📈 上升 (+{change:.2f})"
    elif change < 0:
        trend = f"📉 下降 ({change:.2f})"
    else:
        trend = f"➡️ 持平"
    lines.append(f"趋势: {trend}")

    # 阈值状态
    threshold_status = []
    for threshold in THRESHOLDS:
        distance = threshold - today7
        if distance <= 0:
            threshold_status.append(f"{threshold}✅")
        elif distance <= 5:
            threshold_status.append(f"{threshold}⚠️({distance:.1f})")
        else:
            threshold_status.append(f"{threshold}😴({distance:.1f})")

    lines.append(f"阈值状态: {' '.join(threshold_status)}")

    # 特殊情况说明
    if fired_levels and not final_levels:
        lines.append("🔒 有信号触发但处于冷却期")

    # 冷却状态
    cooldown_info = get_cooldown_info(state)
    if cooldown_info:
        lines.append(f"冷却状态: {cooldown_info}")

    lines.append("🤖 系统运行正常")

    return "\n".join(lines)


def get_cooldown_status(state):
    """获取冷却状态字典"""
    status = {}
    last_triggers = state.get('last_trigger_at', {})
    today = today_utc_date()  # 添加今天的日期

    for threshold in ['70', '80', '90']:
        last_trigger = last_triggers.get(threshold)
        if last_trigger:
            days_passed = days_since(last_trigger, today)  # 传入两个参数
            remaining = max(0, COOLDOWN_DAYS - days_passed)
            status[threshold] = remaining
        else:
            status[threshold] = 0  # 从未触发，无冷却

    return status


def get_cooldown_info(state):
    """获取冷却信息字符串"""
    status = get_cooldown_status(state)

    cooling_down = []
    for threshold, remaining in status.items():
        if remaining > 0:
            cooling_down.append(f"{threshold}({remaining}天)")

    if cooling_down:
        return f"冷却中: {', '.join(cooling_down)}"
    else:
        return "全部可触发"


def run_bot_mode():
    """运行Bot命令模式 - 已禁用"""
    print("🤖 Bot命令模式已禁用")
    print("原因：事件循环兼容性问题")
    print("")
    print("📊 可用的替代方案：")
    print("  1. 使用定时汇报获取数据（早中晚三次）")
    print("  2. 运行 python test_commands.py 测试所有命令")
    print("  3. 手动调用汇报函数：")
    print("     from src.report_generator import get_status_report")
    print("     print(get_status_report())")
    print("")
    print("💡 核心监控和定时汇报功能不受影响")
    return 1


def run_scheduled_mode():
    """运行定时汇报模式"""
    print("⏰ 启动FGI定时汇报模式...")

    try:
        scheduled_reports_handler = get_scheduled_reports_handler()
        results = scheduled_reports_handler.run_scheduled_reports_sync()

        if "error" in results:
            print(f"❌ 定时汇报失败: {results['error']}")
            return 1

        # 输出结果
        if results:
            for report_type, success in results.items():
                status = "✅ 成功" if success else "❌ 失败"
                print(f"📊 {report_type}汇报: {status}")
        else:
            print("ℹ️ 当前时段无需发送汇报")

        return 0
    except Exception as e:
        print(f"❌ 定时汇报异常: {e}")
        return 1


if __name__ == "__main__":
    # 从命令行参数获取运行模式
    mode = "monitor"  # 默认监控模式

    if len(sys.argv) > 1:
        mode = sys.argv[1]

    # 检查环境变量的运行模式配置
    env_mode = os.getenv('FGI_RUN_MODE')
    if env_mode:
        mode = env_mode

    print(f"🚀 FGI监控系统启动 - 模式: {mode}")

    sys.exit(main(mode))
