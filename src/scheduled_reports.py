#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FGI监控系统 - 定时汇报模块
处理早中晚三个时段的定时汇报逻辑
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List

# 导入telegram相关库
try:
    from telegram import Bot
    from telegram.constants import ParseMode
except ImportError:
    print("❌ 缺少 python-telegram-bot 库，请安装: pip install python-telegram-bot==21.5")
    sys.exit(1)

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    SCHEDULED_REPORTS_ENABLED,
    MORNING_REPORT_UTC,
    NOON_REPORT_UTC,
    EVENING_REPORT_UTC,
)
from src.report_generator import (
    report_generator,
    get_scheduled_report,
)


class ScheduledReportsHandler:
    """定时汇报处理器"""

    def __init__(self):
        """初始化定时汇报处理器"""
        self.bot_token = None
        self.chat_id = None
        self.bot = None

        # 配置日志
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> bool:
        """初始化定时汇报功能"""
        if not SCHEDULED_REPORTS_ENABLED:
            self.logger.info("定时汇报功能已禁用")
            return False

        # 获取环境变量
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if not self.bot_token:
            self.logger.error("缺少 TELEGRAM_BOT_TOKEN 环境变量")
            return False

        if not self.chat_id:
            self.logger.error("缺少 TELEGRAM_CHAT_ID 环境变量")
            return False

        try:
            # 创建Bot实例
            self.bot = Bot(token=self.bot_token)
            self.logger.info("定时汇报初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"定时汇报初始化失败: {e}")
            return False

    async def send_scheduled_report(self, report_type: str) -> bool:
        """发送定时汇报"""
        if not self.bot:
            self.logger.error("Bot未初始化")
            return False

        try:
            # 刷新数据
            if not report_generator.refresh_data():
                self.logger.error("数据刷新失败")
                return False

            # 生成汇报内容
            report_content = get_scheduled_report(report_type)
            if not report_content:
                self.logger.warning(f"无法生成{report_type}汇报")
                return False

            # 发送消息
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"```\n{report_content}\n```",
                parse_mode=ParseMode.MARKDOWN_V2
            )

            self.logger.info(f"{report_type}汇报发送成功")
            return True

        except Exception as e:
            self.logger.error(f"{report_type}汇报发送失败: {e}")
            return False

    def should_send_report(self, report_type: str) -> bool:
        """检查是否应该发送指定类型的汇报"""
        current_utc_hour = datetime.utcnow().hour

        if report_type == "morning":
            return current_utc_hour == MORNING_REPORT_UTC
        elif report_type == "noon":
            return current_utc_hour == NOON_REPORT_UTC
        elif report_type == "evening":
            return current_utc_hour == EVENING_REPORT_UTC

        return False

    async def process_scheduled_reports(self) -> Dict[str, bool]:
        """处理所有到期的定时汇报"""
        if not self.initialize():
            return {"error": "初始化失败"}

        results = {}
        current_utc_hour = datetime.utcnow().hour

        # 检查并发送各个时段的汇报
        report_schedule = {
            "morning": MORNING_REPORT_UTC,
            "noon": NOON_REPORT_UTC,
            "evening": EVENING_REPORT_UTC
        }

        for report_type, scheduled_hour in report_schedule.items():
            if current_utc_hour == scheduled_hour:
                self.logger.info(f"开始发送{report_type}汇报 (UTC {current_utc_hour}:00)")
                results[report_type] = await self.send_scheduled_report(report_type)
            else:
                self.logger.debug(f"{report_type}汇报非当前时段 (当前: UTC {current_utc_hour}, 预定: UTC {scheduled_hour})")

        return results

    def run_scheduled_reports_sync(self) -> Dict[str, bool]:
        """同步运行定时汇报（用于测试和外部调用）"""
        try:
            return asyncio.run(self.process_scheduled_reports())
        except Exception as e:
            self.logger.error(f"定时汇报运行失败: {e}")
            return {"error": str(e)}


# 全局实例
scheduled_reports_handler = ScheduledReportsHandler()


def get_current_report_type() -> Optional[str]:
    """获取当前时段应该发送的汇报类型"""
    current_utc_hour = datetime.utcnow().hour

    if current_utc_hour == MORNING_REPORT_UTC:
        return "morning"
    elif current_utc_hour == NOON_REPORT_UTC:
        return "noon"
    elif current_utc_hour == EVENING_REPORT_UTC:
        return "evening"

    return None


async def send_current_scheduled_report() -> Optional[bool]:
    """发送当前时段的定时汇报"""
    report_type = get_current_report_type()
    if not report_type:
        return None

    if not scheduled_reports_handler.initialize():
        return False

    return await scheduled_reports_handler.send_scheduled_report(report_type)


def is_scheduled_reports_enabled() -> bool:
    """检查定时汇报是否启用"""
    return (SCHEDULED_REPORTS_ENABLED and
            os.getenv('TELEGRAM_BOT_TOKEN') is not None and
            os.getenv('TELEGRAM_CHAT_ID') is not None)


def get_next_report_time() -> Optional[str]:
    """获取下次汇报时间"""
    if not is_scheduled_reports_enabled():
        return None

    current_utc = datetime.utcnow()
    current_hour = current_utc.hour

    report_hours = sorted([MORNING_REPORT_UTC, NOON_REPORT_UTC, EVENING_REPORT_UTC])

    # 找到下个汇报时间
    for hour in report_hours:
        if hour > current_hour:
            next_report = current_utc.replace(hour=hour, minute=0, second=0, microsecond=0)
            return next_report.strftime("%Y-%m-%d %H:%M UTC")

    # 如果今天没有更多汇报时间，返回明天的第一个汇报时间
    tomorrow = current_utc + timedelta(days=1)
    next_report = tomorrow.replace(hour=min(report_hours), minute=0, second=0, microsecond=0)
    return next_report.strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    # 测试定时汇报功能
    print("🕐 FGI定时汇报模块测试")

    if not is_scheduled_reports_enabled():
        print("❌ 定时汇报功能未启用或缺少配置")
        print("需要设置环境变量:")
        print("- TELEGRAM_BOT_TOKEN")
        print("- TELEGRAM_CHAT_ID")
        sys.exit(1)

    print("✅ 定时汇报配置检查通过")

    current_report_type = get_current_report_type()
    if current_report_type:
        print(f"⏰ 当前时段需要发送{current_report_type}汇报")

        # 运行定时汇报
        results = scheduled_reports_handler.run_scheduled_reports_sync()
        if "error" in results:
            print(f"❌ 定时汇报失败: {results['error']}")
            sys.exit(1)
        else:
            for report_type, success in results.items():
                status = "✅ 成功" if success else "❌ 失败"
                print(f"📊 {report_type}汇报: {status}")
    else:
        print(f"ℹ️ 当前时段无需发送汇报")
        next_time = get_next_report_time()
        if next_time:
            print(f"⏰ 下次汇报时间: {next_time}")