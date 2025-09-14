#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FGI监控系统 - Telegram Bot命令处理器
处理用户发送的Telegram命令，提供交互式FGI数据查询
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set
from collections import defaultdict

# 导入telegram相关库
try:
    from telegram import Update, BotCommand
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.constants import ParseMode
except ImportError:
    print("❌ 缺少 python-telegram-bot 库，请安装: pip install python-telegram-bot==21.5")
    sys.exit(1)

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    BOT_COMMANDS_ENABLED,
    BOT_ADMIN_ONLY,
    BOT_RATE_LIMIT,
    BOT_COMMANDS,
)
from src.report_generator import (
    report_generator,
    get_status_report,
    get_detailed_report,
    get_trend_report,
)


class FGIBotHandler:
    """FGI Bot命令处理器"""

    def __init__(self):
        """初始化Bot处理器"""
        self.app = None
        self.bot_token = None
        self.admin_id = None
        self.rate_limiter = defaultdict(list)  # 用户ID -> 命令时间列表

        # 配置日志
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> bool:
        """初始化Bot"""
        if not BOT_COMMANDS_ENABLED:
            self.logger.info("Bot命令功能已禁用")
            return False

        # 获取环境变量
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        admin_id_str = os.getenv('TELEGRAM_BOT_ADMIN_ID')

        if not self.bot_token:
            self.logger.error("缺少 TELEGRAM_BOT_TOKEN 环境变量")
            return False

        if BOT_ADMIN_ONLY and not admin_id_str:
            self.logger.error("启用管理员模式但缺少 TELEGRAM_BOT_ADMIN_ID 环境变量")
            return False

        if admin_id_str:
            try:
                self.admin_id = int(admin_id_str)
            except ValueError:
                self.logger.error("TELEGRAM_BOT_ADMIN_ID 必须是数字")
                return False

        # 创建Application
        try:
            self.app = Application.builder().token(self.bot_token).build()
            self.logger.info("Bot初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"Bot初始化失败: {e}")
            return False

    def setup_handlers(self):
        """设置命令处理器"""
        if not self.app:
            return

        # 添加命令处理器
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("fgi", self.fgi_command))
        self.app.add_handler(CommandHandler("trend", self.trend_command))

        # 添加消息处理器（处理非命令消息）
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # 添加错误处理器
        self.app.add_error_handler(self.error_handler)

        self.logger.info("命令处理器设置完成")

    async def setup_bot_commands(self):
        """设置Bot菜单命令"""
        if not self.app:
            return

        try:
            commands = [
                BotCommand("start", "开始使用FGI监控Bot"),
                BotCommand("help", "显示帮助信息"),
                BotCommand("status", "获取当前FGI状态概览"),
                BotCommand("fgi", "获取详细FGI数据分析"),
                BotCommand("trend", "获取FGI趋势分析"),
            ]

            await self.app.bot.set_my_commands(commands)
            self.logger.info("Bot菜单命令设置成功")

        except Exception as e:
            self.logger.error(f"设置Bot菜单命令失败: {e}")

    def check_permission(self, user_id: int) -> bool:
        """检查用户权限"""
        # 确保已初始化
        if self.admin_id is None and BOT_ADMIN_ONLY:
            self.initialize()

        if not BOT_ADMIN_ONLY:
            return True

        # 调试输出
        if hasattr(self, 'logger'):
            self.logger.debug(f"检查权限: user_id={user_id}, admin_id={self.admin_id}, BOT_ADMIN_ONLY={BOT_ADMIN_ONLY}")

        return user_id == self.admin_id

    def check_rate_limit(self, user_id: int) -> bool:
        """检查速率限制"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # 清理过期的请求记录
        self.rate_limiter[user_id] = [
            req_time for req_time in self.rate_limiter[user_id]
            if req_time > minute_ago
        ]

        # 检查是否超过限制
        if len(self.rate_limiter[user_id]) >= BOT_RATE_LIMIT:
            return False

        # 记录本次请求
        self.rate_limiter[user_id].append(now)
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name

        if not self.check_permission(user_id):
            await update.message.reply_text("❌ 抱歉，您没有使用此Bot的权限")
            return

        welcome_message = f"""
🤖 欢迎使用 FGI 监控 Bot！

👋 你好 {user_name}！

我是专业的恐慌贪婪指数监控助手，可以为您提供：

📊 实时FGI数据查询
📈 详细趋势分析
🎯 阈值状态监控
⚠️ 智能提醒服务

🔧 可用命令：
/status - 获取FGI状态概览
/fgi - 获取详细数据分析
/trend - 获取趋势分析
/help - 显示帮助信息

💡 直接发送命令即可开始使用！
        """

        await update.message.reply_text(welcome_message.strip())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        user_id = update.effective_user.id

        if not self.check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用权限")
            return

        help_message = """
🆘 FGI监控Bot使用帮助

📋 可用命令：

/status
📊 获取当前FGI状态概览
• 当前FGI值和FGI7
• 趋势变化
• 市场情绪判断
• 下个阈值距离

/fgi
📈 获取详细FGI数据分析
• 完整数据展示
• 阈值分析详情
• 冷却状态信息
• 最近趋势分析

/trend
📊 获取FGI趋势分析
• 短期趋势（7天）
• 中期趋势（14天）
• 关键水平分析
• 技术指标判断

/help
🆘 显示此帮助信息

⚡ 使用技巧：
• 命令响应时间约2-5秒
• 数据每小时更新
• 支持快速连续查询
• 所有时间为UTC时区

📞 技术支持：
如有问题请联系管理员
        """

        await update.message.reply_text(help_message.strip())

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        user_id = update.effective_user.id

        if not self.check_permission(user_id):
            await update.message.reply_text("❌ 权限不足")
            return

        if not self.check_rate_limit(user_id):
            await update.message.reply_text("⚠️ 请求过于频繁，请稍后再试")
            return

        # 发送"正在处理"消息
        processing_msg = await update.message.reply_text("⏳ 正在获取FGI状态...")

        try:
            # 获取状态汇报
            report = get_status_report()

            # 更新消息内容
            await processing_msg.edit_text(f"```\n{report}\n```", parse_mode=ParseMode.MARKDOWN_V2)

        except Exception as e:
            self.logger.error(f"状态命令处理失败: {e}")
            await processing_msg.edit_text("❌ 获取FGI状态失败，请稍后重试")

    async def fgi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /fgi 命令"""
        user_id = update.effective_user.id

        if not self.check_permission(user_id):
            await update.message.reply_text("❌ 权限不足")
            return

        if not self.check_rate_limit(user_id):
            await update.message.reply_text("⚠️ 请求过于频繁，请稍后再试")
            return

        # 发送处理消息
        processing_msg = await update.message.reply_text("⏳ 正在分析FGI数据...")

        try:
            # 获取详细汇报
            report = get_detailed_report()

            # 由于消息可能很长，需要分段发送或使用代码块格式
            if len(report) > 4000:  # Telegram消息长度限制
                # 分段发送
                parts = self._split_message(report, 3900)
                await processing_msg.edit_text(f"```\n{parts[0]}\n```", parse_mode=ParseMode.MARKDOWN_V2)

                for i, part in enumerate(parts[1:], 2):
                    await update.message.reply_text(f"```\n{part}\n```", parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await processing_msg.edit_text(f"```\n{report}\n```", parse_mode=ParseMode.MARKDOWN_V2)

        except Exception as e:
            self.logger.error(f"FGI命令处理失败: {e}")
            await processing_msg.edit_text("❌ 获取FGI数据失败，请稍后重试")

    async def trend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /trend 命令"""
        user_id = update.effective_user.id

        if not self.check_permission(user_id):
            await update.message.reply_text("❌ 权限不足")
            return

        if not self.check_rate_limit(user_id):
            await update.message.reply_text("⚠️ 请求过于频繁，请稍后再试")
            return

        # 发送处理消息
        processing_msg = await update.message.reply_text("⏳ 正在分析趋势...")

        try:
            # 获取趋势分析
            report = get_trend_report()

            await processing_msg.edit_text(f"```\n{report}\n```", parse_mode=ParseMode.MARKDOWN_V2)

        except Exception as e:
            self.logger.error(f"趋势命令处理失败: {e}")
            await processing_msg.edit_text("❌ 获取趋势分析失败，请稍后重试")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理非命令消息"""
        user_id = update.effective_user.id

        if not self.check_permission(user_id):
            return  # 静默忽略无权限用户的消息

        # 简单的智能回复
        message_text = update.message.text.lower()

        if any(word in message_text for word in ['fgi', '恐慌', '贪婪', '指数']):
            await update.message.reply_text("📊 请使用 /fgi 命令获取详细的FGI数据分析")
        elif any(word in message_text for word in ['趋势', '分析', '走势']):
            await update.message.reply_text("📈 请使用 /trend 命令获取FGI趋势分析")
        elif any(word in message_text for word in ['状态', '现在', '当前']):
            await update.message.reply_text("📊 请使用 /status 命令获取当前FGI状态")
        elif any(word in message_text for word in ['帮助', 'help', '命令']):
            await update.message.reply_text("🆘 请使用 /help 命令查看使用帮助")
        else:
            await update.message.reply_text("🤖 请使用 /help 查看可用命令")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """错误处理器"""
        self.logger.error(f"Bot发生错误: {context.error}")

        if update and update.message:
            try:
                await update.message.reply_text("❌ 处理请求时发生错误，请稍后重试")
            except Exception:
                pass  # 忽略发送错误消息的失败

    def _split_message(self, text: str, max_length: int = 3900) -> list:
        """分割长消息"""
        if len(text) <= max_length:
            return [text]

        parts = []
        lines = text.split('\n')
        current_part = ""

        for line in lines:
            if len(current_part + line + '\n') <= max_length:
                current_part += line + '\n'
            else:
                if current_part:
                    parts.append(current_part.rstrip('\n'))
                    current_part = line + '\n'
                else:
                    # 单行太长，强制分割
                    parts.append(line[:max_length])
                    current_part = line[max_length:] + '\n'

        if current_part:
            parts.append(current_part.rstrip('\n'))

        return parts

    async def run_polling(self):
        """运行Bot（轮询模式）"""
        if not self.app:
            self.logger.error("Bot未初始化")
            return

        try:
            # 设置Bot命令菜单
            await self.setup_bot_commands()

            # 开始轮询
            self.logger.info("开始Bot轮询...")
            await self.app.run_polling()

        except Exception as e:
            self.logger.error(f"Bot运行失败: {e}")
            raise

    def run_bot_sync(self):
        """同步运行Bot（用于测试）"""
        if not self.initialize():
            return False

        self.setup_handlers()

        try:
            # 先设置Bot命令菜单（同步方式）
            asyncio.run(self.setup_bot_commands())

            # 简化的运行方式 - 让 python-telegram-bot 自己管理事件循环
            self.logger.info("开始Bot轮询...")
            self.app.run_polling()
            return True
        except KeyboardInterrupt:
            self.logger.info("Bot已停止")
            return True
        except Exception as e:
            self.logger.error(f"Bot运行异常: {e}")
            return False


# 全局Bot实例
bot_handler = FGIBotHandler()


async def process_bot_command(command: str, user_id: int = None) -> str:
    """处理Bot命令（供外部调用）"""
    try:
        # 刷新数据
        report_generator.refresh_data()

        if command == "status":
            return get_status_report()
        elif command == "fgi":
            return get_detailed_report()
        elif command == "trend":
            return get_trend_report()
        elif command == "help":
            return """
🆘 FGI监控Bot帮助

可用命令：
/status - FGI状态概览
/fgi - 详细数据分析
/trend - 趋势分析
/help - 显示帮助

所有数据基于alternative.me API
            """.strip()
        else:
            return "❌ 未知命令，请使用 /help 查看可用命令"

    except Exception as e:
        logging.error(f"处理命令失败: {e}")
        return "❌ 处理命令时发生错误"


def is_bot_enabled() -> bool:
    """检查Bot是否启用"""
    return BOT_COMMANDS_ENABLED and os.getenv('TELEGRAM_BOT_TOKEN') is not None


if __name__ == "__main__":
    # 测试Bot功能
    print("🤖 FGI Bot命令处理器测试")

    if not is_bot_enabled():
        print("❌ Bot功能未启用或缺少配置")
        sys.exit(1)

    print("✅ Bot配置检查通过")
    print("🚀 启动Bot...")

    try:
        bot_handler.run_bot_sync()
    except Exception as e:
        print(f"❌ Bot运行失败: {e}")
        sys.exit(1)