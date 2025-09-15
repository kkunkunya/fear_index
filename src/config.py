# FGI恐慌贪婪指数监控项目配置文件
# 包含API地址、策略参数、冷却设置等所有配置项

# API数据源配置
FGI_API = "https://api.alternative.me/fng/?limit=14&format=json"

# 策略阈值配置 - 顺序重要，用于跨级同日触发
THRESHOLDS = [70, 80, 90]

# 分层卖出比例映射 - 每个阈值对应的卖出百分比
SELL_MAP = {70: 10, 80: 15, 90: 25}

# 冷却机制配置
COOLDOWN_DAYS = 7  # 每个阈值独立7天冷却期

# 最小卖出阈值 - 低于此值不触发任何卖出信号
MIN_SELL_LEVEL = 60

# 时区配置 - 状态日期使用UTC自然日
TIMEZONE = "UTC"

# 首次上线配置 - 上线首日不触发历史信号，避免补发
BOOTSTRAP_SUPPRESS_FIRST_DAY = True

# 汇报功能配置
ENABLE_DAILY_REPORT = True  # 是否启用每日数据汇报（即使无触发）
VERBOSE_MODE = False  # 是否启用详细模式（显示更多调试信息）
REPORT_THRESHOLD_DISTANCE = 10  # 当FGI7距离阈值小于此值时发送接近提醒

# Telegram Bot配置
BOT_COMMANDS_ENABLED = True  # 是否启用Bot命令功能
BOT_ADMIN_ONLY = True  # 是否限制仅管理员可使用Bot命令
BOT_RATE_LIMIT = 5  # Bot命令使用频率限制（每分钟最多次数）

# 定时汇报配置
SCHEDULED_REPORTS_ENABLED = True  # 是否启用定时汇报
MORNING_REPORT_UTC = 0  # 早报时间 (UTC小时，对应北京08:00)
NOON_REPORT_UTC = 4  # 午报时间 (UTC小时，对应北京12:00)
EVENING_REPORT_UTC = 12  # 晚报时间 (UTC小时，对应北京20:00)

# Bot命令配置
BOT_COMMANDS = {
    "status": "获取当前FGI状态概览",
    "fgi": "获取详细FGI数据和分析",
    "trend": "获取FGI趋势分析",
    "help": "显示可用命令帮助",
}
