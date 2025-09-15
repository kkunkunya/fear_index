#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FGI监控系统 - 统一汇报生成器
负责生成各种类型的FGI数据汇报，供不同场景使用
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    THRESHOLDS,
    SELL_MAP,
    COOLDOWN_DAYS,
    REPORT_THRESHOLD_DISTANCE,
)
from src.state import load_state, days_since, today_utc_date
from src.strategy import compute_fgi7, crossings, two_consecutive_ge


# 避免循环导入，动态导入 fetch_fgi
def fetch_fgi():
    """动态导入并调用fetch_fgi函数"""
    from src.fgi_notifier import fetch_fgi as _fetch_fgi

    return _fetch_fgi()


class FGIReportGenerator:
    """FGI汇报生成器类"""

    def __init__(self):
        """初始化汇报生成器"""
        self.data = None
        self.prev7 = None
        self.today7 = None
        self.latest_fgi = None
        self.latest_date = None
        self.state = None

    def refresh_data(self):
        """刷新FGI数据"""
        try:
            # 获取最新数据
            self.data = fetch_fgi()
            self.prev7, self.today7 = compute_fgi7(self.data)
            self.latest_fgi = self.data[-1][1] if self.data else None
            self.latest_date = self.data[-1][0] if self.data else None
            self.state = load_state()

            return True
        except Exception as e:
            print(f"数据刷新失败: {e}")
            return False

    def generate_status_report(self) -> str:
        """生成状态概览汇报"""
        if not self._ensure_data():
            return "❌ 数据获取失败，无法生成状态汇报"

        lines = []
        lines.append("📊 FGI状态概览")
        lines.append(f"📅 日期: {self.latest_date}")
        lines.append(f"📈 当前FGI: {self.latest_fgi}")
        lines.append(f"📊 FGI7: {self.today7:.2f}")

        # 趋势判断
        change = self.today7 - self.prev7
        if change > 0:
            trend = f"📈 上升 (+{change:.2f})"
        elif change < 0:
            trend = f"📉 下降 ({change:.2f})"
        else:
            trend = f"➡️ 持平"
        lines.append(f"📈 趋势: {trend}")

        # 市场情绪
        mood = self._get_market_mood(self.today7)
        lines.append(f"💭 市场情绪: {mood}")

        # 下个阈值距离
        next_threshold_info = self._get_next_threshold_info()
        if next_threshold_info:
            lines.append(f"🎯 下个阈值: {next_threshold_info}")

        return "\n".join(lines)

    def generate_detailed_report(self) -> str:
        """生成详细FGI数据分析汇报"""
        if not self._ensure_data():
            return "❌ 数据获取失败，无法生成详细汇报"

        lines = []
        lines.append("📊 FGI详细数据分析")
        lines.append(f"📅 日期: {self.latest_date} (UTC)")
        lines.append("")

        # 当前数据
        lines.append("📈 当前数据:")
        lines.append(f"  • 今日FGI: {self.latest_fgi}")
        lines.append(f"  • FGI7: {self.today7:.2f} (昨日: {self.prev7:.2f})")

        change = self.today7 - self.prev7
        change_str = f"{change:+.2f}"
        lines.append(f"  • 变化: {change_str}")

        # 阈值分析
        lines.append("")
        lines.append("🎯 阈值分析:")
        for threshold in THRESHOLDS:
            distance = threshold - self.today7
            if distance <= 0:
                status = f"✅ 已超过 (+{abs(distance):.2f})"
            elif distance <= 5:
                status = f"⚠️ 接近 (-{distance:.2f})"
            else:
                status = f"😴 较远 (-{distance:.2f})"

            sell_pct = SELL_MAP.get(threshold, 0)
            lines.append(f"  • 阈值{threshold} (卖出{sell_pct}%): {status}")

        # 冷却状态
        cooldown_info = self._get_cooldown_status()
        if cooldown_info:
            lines.append("")
            lines.append("🧊 冷却状态:")
            for info in cooldown_info:
                lines.append(f"  • {info}")

        # 最近趋势
        recent_trend = self._get_recent_trend()
        if recent_trend:
            lines.append("")
            lines.append("📈 最近趋势:")
            lines.append(recent_trend)

        return "\n".join(lines)

    def generate_trend_report(self) -> str:
        """生成趋势分析汇报"""
        if not self._ensure_data():
            return "❌ 数据获取失败，无法生成趋势分析"

        lines = []
        lines.append("📈 FGI趋势分析")
        lines.append(f"📅 分析日期: {self.latest_date}")
        lines.append("")

        # 短期趋势（7天）
        short_trend = self._analyze_short_trend()
        lines.append("📊 短期趋势 (7天):")
        lines.append(short_trend)

        # 中期趋势（14天）
        medium_trend = self._analyze_medium_trend()
        lines.append("")
        lines.append("📊 中期趋势 (14天):")
        lines.append(medium_trend)

        # 关键水平分析
        key_levels = self._analyze_key_levels()
        lines.append("")
        lines.append("🔑 关键水平:")
        lines.append(key_levels)

        return "\n".join(lines)

    def generate_scheduled_report(self, report_type: str) -> Optional[str]:
        """生成定时汇报"""
        if not self._ensure_data():
            return None

        current_hour = datetime.utcnow().hour

        if report_type == "morning":
            return self._generate_morning_report()
        elif report_type == "noon":
            return self._generate_noon_report()
        elif report_type == "evening":
            return self._generate_evening_report()
        else:
            return None

    def _generate_morning_report(self) -> str:
        """生成早报"""
        lines = []
        lines.append("🌅 FGI晨报")
        lines.append(f"📅 {self.latest_date} (UTC)")
        lines.append("")

        # 隔夜变化
        lines.append("🌙 隔夜市场:")
        lines.append(f"  • 当前FGI: {self.latest_fgi}")
        lines.append(f"  • FGI7: {self.today7:.2f}")

        # 今日关注点
        attention_points = self._get_daily_attention_points()
        if attention_points:
            lines.append("")
            lines.append("👀 今日关注:")
            for point in attention_points:
                lines.append(f"  • {point}")

        lines.append("")
        lines.append("☀️ 祝您交易愉快！")
        return "\n".join(lines)

    def _generate_noon_report(self) -> str:
        """生成午报"""
        lines = []
        # 去除固定分钟标注，避免与调度半点不一致
        lines.append("🌞 FGI午报")
        lines.append(f"📅 {self.latest_date} (UTC)")
        lines.append("")

        # 中期状态
        lines.append("📊 中期状态:")
        lines.append(
            f"  • FGI7: {self.today7:.2f} ({self.prev7:.2f} → {self.today7:.2f})"
        )

        mood = self._get_market_mood(self.today7)
        lines.append(f"  • 市场情绪: {mood}")

        # 阈值状态
        threshold_alert = self._get_threshold_alerts()
        if threshold_alert:
            lines.append("")
            lines.append("⚠️ 阈值提醒:")
            lines.append(f"  • {threshold_alert}")

        return "\n".join(lines)

    def _generate_evening_report(self) -> str:
        """生成晚报"""
        lines = []
        # 去除固定分钟标注，避免与调度半点不一致
        lines.append("🌅 FGI晚报")
        lines.append(f"📅 {self.latest_date} (UTC)")
        lines.append("")

        # 全日总结
        lines.append("📊 今日总结:")
        lines.append(f"  • FGI: {self.latest_fgi}")
        lines.append(f"  • FGI7: {self.prev7:.2f} → {self.today7:.2f}")

        change = self.today7 - self.prev7
        if abs(change) >= 2:
            change_desc = "显著" if abs(change) >= 5 else "明显"
            direction = "上升" if change > 0 else "下降"
            lines.append(f"  • 变化: {change_desc}{direction} ({change:+.2f})")

        # 明日展望
        outlook = self._get_tomorrow_outlook()
        if outlook:
            lines.append("")
            lines.append("🔮 明日展望:")
            lines.append(f"  • {outlook}")

        lines.append("")
        lines.append("🌙 晚安，明日见！")
        return "\n".join(lines)

    def _ensure_data(self) -> bool:
        """确保数据已加载"""
        if self.data is None:
            return self.refresh_data()
        return True

    def _get_market_mood(self, fgi7_value: float) -> str:
        """获取市场情绪描述"""
        if fgi7_value >= 75:
            return "🔥 极度贪婪"
        elif fgi7_value >= 55:
            return "📈 贪婪"
        elif fgi7_value >= 45:
            return "⚖️ 中性"
        elif fgi7_value >= 25:
            return "📉 恐惧"
        else:
            return "🥶 极度恐惧"

    def _get_next_threshold_info(self) -> Optional[str]:
        """获取下个阈值信息"""
        for threshold in THRESHOLDS:
            if self.today7 < threshold:
                distance = threshold - self.today7
                sell_pct = SELL_MAP.get(threshold, 0)
                return f"距离{threshold}阈值还有{distance:.1f}点 (卖出{sell_pct}%)"
        return None

    def _get_cooldown_status(self) -> List[str]:
        """获取冷却状态信息"""
        status_list = []
        last_triggers = self.state.get("last_trigger_at", {})
        today = today_utc_date()

        for threshold in ["70", "80", "90"]:
            last_trigger = last_triggers.get(threshold)
            if last_trigger:
                days_passed = days_since(last_trigger, today)
                remaining = max(0, COOLDOWN_DAYS - days_passed)
                if remaining > 0:
                    status_list.append(f"阈值{threshold}: 冷却中 (还需{remaining}天)")
                else:
                    status_list.append(f"阈值{threshold}: ✅ 可触发")
            else:
                status_list.append(f"阈值{threshold}: ✅ 可触发 (从未触发)")

        return status_list

    def _get_recent_trend(self) -> str:
        """获取最近趋势信息"""
        if len(self.data) < 3:
            return "数据不足"

        # 分析最近3天的趋势
        recent_values = [fgi for _, fgi in self.data[-3:]]

        if recent_values[2] > recent_values[1] > recent_values[0]:
            return "📈 连续上升趋势"
        elif recent_values[2] < recent_values[1] < recent_values[0]:
            return "📉 连续下降趋势"
        elif recent_values[2] > recent_values[0]:
            return "📈 整体上升"
        elif recent_values[2] < recent_values[0]:
            return "📉 整体下降"
        else:
            return "➡️ 相对稳定"

    def _analyze_short_trend(self) -> str:
        """分析短期趋势"""
        if len(self.data) < 7:
            return "  数据不足"

        # 计算7天内的变化
        week_ago_fgi = self.data[-7][1]
        change = self.latest_fgi - week_ago_fgi

        lines = []
        lines.append(f"  • 7天前FGI: {week_ago_fgi}")
        lines.append(f"  • 当前FGI: {self.latest_fgi}")
        lines.append(f"  • 变化: {change:+.1f}")

        if abs(change) >= 10:
            intensity = "强烈"
        elif abs(change) >= 5:
            intensity = "明显"
        else:
            intensity = "温和"

        direction = "上升" if change > 0 else "下降" if change < 0 else "持平"
        lines.append(f"  • 趋势: {intensity}{direction}")

        return "\n".join(lines)

    def _analyze_medium_trend(self) -> str:
        """分析中期趋势"""
        if len(self.data) < 14:
            return "  数据不足"

        # 计算14天内的最高、最低和平均值
        two_weeks_data = [fgi for _, fgi in self.data[-14:]]
        max_fgi = max(two_weeks_data)
        min_fgi = min(two_weeks_data)
        avg_fgi = sum(two_weeks_data) / len(two_weeks_data)

        lines = []
        lines.append(f"  • 14天最高: {max_fgi}")
        lines.append(f"  • 14天最低: {min_fgi}")
        lines.append(f"  • 14天均值: {avg_fgi:.1f}")
        lines.append(f"  • 当前位置: {self.latest_fgi}")

        # 判断当前位置
        range_size = max_fgi - min_fgi
        current_position = (
            (self.latest_fgi - min_fgi) / range_size if range_size > 0 else 0.5
        )

        if current_position > 0.8:
            position_desc = "高位区间"
        elif current_position > 0.6:
            position_desc = "中高位区间"
        elif current_position > 0.4:
            position_desc = "中位区间"
        elif current_position > 0.2:
            position_desc = "中低位区间"
        else:
            position_desc = "低位区间"

        lines.append(f"  • 区间位置: {position_desc}")

        return "\n".join(lines)

    def _analyze_key_levels(self) -> str:
        """分析关键水平"""
        lines = []

        # 分析相对于阈值的位置
        for threshold in THRESHOLDS:
            distance = threshold - self.today7
            sell_pct = SELL_MAP.get(threshold, 0)

            if distance <= 0:
                lines.append(f"  • {threshold}阈值: ✅ 已突破 (卖出{sell_pct}%)")
            elif distance <= 5:
                lines.append(f"  • {threshold}阈值: ⚠️ 临近 ({distance:.1f}点)")
            else:
                lines.append(f"  • {threshold}阈值: 😴 较远 ({distance:.1f}点)")

        return "\n".join(lines)

    def _get_daily_attention_points(self) -> List[str]:
        """获取今日关注点"""
        points = []

        # 检查是否接近阈值
        for threshold in THRESHOLDS:
            distance = threshold - self.today7
            if 0 < distance <= REPORT_THRESHOLD_DISTANCE:
                points.append(f"接近{threshold}阈值 (还有{distance:.1f}点)")

        # 检查冷却状态
        last_triggers = self.state.get("last_trigger_at", {})
        today = today_utc_date()

        for threshold_str in ["70", "80", "90"]:
            last_trigger = last_triggers.get(threshold_str)
            if last_trigger:
                days_passed = days_since(last_trigger, today)
                if days_passed == COOLDOWN_DAYS:
                    points.append(f"{threshold_str}阈值冷却期结束，重新激活")

        # 如果没有特别关注点，添加通用关注
        if not points:
            mood = self._get_market_mood(self.today7)
            points.append(f"市场情绪{mood}，保持关注")

        return points

    def _get_threshold_alerts(self) -> Optional[str]:
        """获取阈值警报"""
        for threshold in THRESHOLDS:
            distance = threshold - self.today7
            if 0 < distance <= 5:  # 距离阈值5点以内
                return f"距离{threshold}阈值仅{distance:.1f}点"
        return None

    def _get_tomorrow_outlook(self) -> Optional[str]:
        """获取明日展望"""
        # 基于当前趋势给出简单展望
        change = self.today7 - self.prev7

        if abs(change) < 1:
            return "趋势相对稳定，关注突破方向"
        elif change > 0:
            next_threshold = None
            for threshold in THRESHOLDS:
                if self.today7 < threshold:
                    next_threshold = threshold
                    break
            if next_threshold:
                distance = next_threshold - self.today7
                if distance <= 10:
                    return f"上升趋势中，关注{next_threshold}阈值突破"
            return "上升趋势中，保持关注"
        else:
            return "下降趋势中，关注支撑水平"


# 全局实例
report_generator = FGIReportGenerator()


# 便捷函数
def get_status_report() -> str:
    """获取状态概览汇报"""
    return report_generator.generate_status_report()


def get_detailed_report() -> str:
    """获取详细汇报"""
    return report_generator.generate_detailed_report()


def get_trend_report() -> str:
    """获取趋势分析汇报"""
    return report_generator.generate_trend_report()


def get_scheduled_report(report_type: str) -> Optional[str]:
    """获取定时汇报"""
    return report_generator.generate_scheduled_report(report_type)


if __name__ == "__main__":
    # 测试功能
    print("🧪 测试汇报生成器...")

    try:
        # 刷新数据
        if report_generator.refresh_data():
            print("✅ 数据刷新成功")

            # 测试各种汇报
            print("\n" + "=" * 50)
            print("状态概览测试:")
            print(get_status_report())

            print("\n" + "=" * 50)
            print("详细汇报测试:")
            print(get_detailed_report())

            print("\n" + "=" * 50)
            print("趋势分析测试:")
            print(get_trend_report())

        else:
            print("❌ 数据刷新失败")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        raise
