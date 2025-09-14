# FGI恐慌贪婪指数监控项目

## 项目简介

本项目是一个基于GitHub Actions的24/7自动化加密货币Fear & Greed Index (FGI)监控系统。通过实时跟踪alternative.me提供的FGI数据，计算7天滑动平均值(FGI7)，并在特定阈值触发时通过Telegram发送卖出提醒。

### 核心功能

- **自动化数据获取**: 每小时从alternative.me API获取最新FGI数据
- **FGI7计算**: 计算7天滑动平均值，减少短期波动噪音
- **分层卖出策略**: 在70/80/90阈值触发不同比例的卖出信号
- **冷却机制**: 每个阈值独立7天冷却期，避免重复通知
- **状态持久化**: 自动保存处理状态，支持断点续传
- **Telegram通知**: 实时发送格式化的卖出提醒消息

### 策略逻辑

- **阈值**: FGI7上穿70/80/90时分别触发10%/15%/25%卖出
- **连续检测**: FGI7连续2天≥90时额外触发90阈值
- **跨级触发**: 同日可触发多个阈值(70→80→90)
- **低值保护**: FGI7<60时仅提示，不建议卖出
- **首次上线**: Bootstrap模式避免触发历史信号

## 系统要求

- GitHub仓库(用于GitHub Actions)
- Python 3.11+
- 网络连接(访问alternative.me API)
- Telegram Bot Token和Chat ID

## 快速部署

### 1. 仓库设置

```bash
# 克隆或创建新仓库
git clone <your-repo-url>
cd fear_index

# 确保项目结构完整
mkdir -p src state .github/workflows
```

### 2. 依赖安装(本地测试用)

```bash
pip install -r requirements.txt
```

### 3. Telegram Bot配置

#### 创建Telegram Bot
1. 在Telegram中找到 @BotFather
2. 发送 `/newbot` 创建新bot
3. 记录返回的 `Bot Token`

#### 获取Chat ID
1. 将bot添加到目标群组或私聊
2. 发送任意消息给bot
3. 访问: `https://api.telegram.org/bot<YourBOTToken>/getUpdates`
4. 在返回的JSON中找到 `chat.id`

### 4. GitHub Secrets配置

在GitHub仓库的 Settings > Secrets and variables > Actions 中添加:

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token | `1234567890:ABCDEFGHIJKLMNOP...` |
| `TELEGRAM_CHAT_ID` | 接收消息的Chat ID | `-100123456789` 或 `123456789` |

### 5. 激活GitHub Actions

GitHub Actions工作流已配置为每小时第7分钟自动运行。首次推送代码后会自动激活。

可在仓库的Actions页面查看运行状态和日志。

## 项目结构

```
fear_index/
├── src/                           # 源代码目录
│   ├── config.py                  # 配置参数
│   ├── state.py                   # 状态管理
│   ├── strategy.py                # 策略计算
│   ├── notify.py                  # 通知发送
│   └── fgi_notifier.py           # 主逻辑
├── state/                         # 状态持久化
│   └── state.json                # 运行状态文件
├── .github/workflows/            # GitHub Actions配置
│   └── fgi-notify.yml           # 工作流定义
├── requirements.txt              # Python依赖
└── README.md                    # 本文档
```

## 配置说明

### 核心配置 (src/config.py)

```python
# API数据源
FGI_API = "https://api.alternative.me/fng/?limit=14&format=json"

# 策略阈值 (顺序重要)
THRESHOLDS = [70, 80, 90]

# 卖出比例映射
SELL_MAP = {70: 10, 80: 15, 90: 25}

# 冷却天数
COOLDOWN_DAYS = 7

# 首次运行抑制
BOOTSTRAP_SUPPRESS_FIRST_DAY = True
```

### 状态文件结构 (state/state.json)

```json
{
  "last_processed_date": "2024-01-15",
  "last_trigger_at": {
    "70": "2024-01-10",
    "80": null,
    "90": "2024-01-05"
  },
  "bootstrapped": true
}
```

## 本地测试

### 单独测试模块

```bash
# 测试API数据获取
python -c "from src.fgi_notifier import fetch_fgi; print(fetch_fgi()[-3:])"

# 测试FGI7计算
python -c "
from src.strategy import compute_fgi7
from datetime import date
data = [(date(2024,1,i), 50+i) for i in range(1,15)]
print(compute_fgi7(data))
"

# 测试Telegram发送 (需要设置环境变量)
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python -c "from src.notify import send_telegram; send_telegram('测试消息')"
```

### 完整流程测试

```bash
# 设置环境变量
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# 运行主程序
python src/fgi_notifier.py
```

## GitHub Actions工作流

### 工作流配置 (.github/workflows/fgi-notify.yml)

- **触发**: 每小时第7分钟运行 (`cron: '7 * * * *'`)
- **环境**: Ubuntu latest + Python 3.11
- **步骤**:
  1. 检出代码
  2. 设置Python环境
  3. 安装依赖
  4. 运行FGI监控
  5. 自动提交状态文件更新

### 查看运行日志

1. 进入GitHub仓库页面
2. 点击 "Actions" 标签
3. 选择 "FGI Notifier" 工作流
4. 查看具体运行的详细日志

## 通知消息格式

触发时会发送如下格式的Telegram消息:

```
[卖出提醒] FGI7触发
日期: 2024-01-15 (UTC)
今日FGI7: 75.5 (昨日: 69.2)，今日FGI: 78
触发: 上穿70 → 卖出10%
规则: 同一阈值7天内只执行一次；跨级同日依序触发
数据源: alternative.me
```

## 问题排查

### 1. GitHub Actions运行失败

**检查步骤**:
- 确认 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 已正确设置
- 查看Actions页面的错误日志
- 检查alternative.me API是否可访问

**常见错误**:
- `Failed to fetch FGI data`: API访问失败，通常是网络问题
- `Failed to send notification`: Telegram配置错误或网络问题
- `Insufficient FGI history`: 数据不足，等待API返回更多历史数据

### 2. 未收到Telegram通知

**检查步骤**:
1. 确认Bot Token格式正确 (`数字:字母数字混合`)
2. 确认Chat ID格式正确 (群组ID通常为负数)
3. 确认bot已添加到目标聊天中且有发送消息权限
4. 检查是否处于冷却期 (同一阈值7天内只通知一次)

### 3. 状态文件问题

**症状**: 重复通知或状态丢失

**解决方案**:
- 检查 `state/state.json` 文件是否正确提交
- 确认GitHub Actions有写入权限
- 必要时删除state.json让系统重新初始化

### 4. FGI7计算异常

**症状**: 计算结果不符合预期

**检查方法**:
```bash
# 查看最近7天FGI数据
curl -s "https://api.alternative.me/fng/?limit=7&format=json" | python -m json.tool

# 手动验证FGI7计算
python -c "
import requests
from statistics import mean
r = requests.get('https://api.alternative.me/fng/?limit=7&format=json')
values = [int(x['value']) for x in r.json()['data']]
print(f'FGI7: {round(mean(values), 2)}')
"
```

## 高级配置

### 修改监控频率

编辑 `.github/workflows/fgi-notify.yml`:
```yaml
schedule:
  - cron: '7 */2 * * *'  # 改为每2小时运行
```

### 调整策略参数

编辑 `src/config.py`:
```python
# 修改阈值和卖出比例
THRESHOLDS = [60, 75, 85, 95]
SELL_MAP = {60: 5, 75: 10, 85: 20, 95: 30}

# 修改冷却期
COOLDOWN_DAYS = 5
```

### 添加新的通知渠道

参考 `src/notify.py` 实现新的通知函数，在 `src/fgi_notifier.py` 中调用。

## 安全注意事项

- **Token安全**: 绝不在代码中硬编码Token，仅使用GitHub Secrets
- **权限控制**: Bot仅需发送消息权限，不要给予管理员权限
- **数据隐私**: 状态文件不包含敏感信息，可安全提交到仓库

## 技术架构

### 模块说明

| 模块 | 职责 | 主要函数 |
|------|------|----------|
| `config.py` | 配置管理 | 定义所有配置常量 |
| `state.py` | 状态持久化 | `load_state()`, `save_state()`, `in_cooldown()` |
| `strategy.py` | 策略计算 | `compute_fgi7()`, `crossings()`, `two_consecutive_ge()` |
| `notify.py` | 通知发送 | `send_telegram()` |
| `fgi_notifier.py` | 主逻辑协调 | `fetch_fgi()`, `main()` |

### 数据流程

1. **数据获取**: `fetch_fgi()` → alternative.me API
2. **策略计算**: `compute_fgi7()` → FGI7滑动平均
3. **信号检测**: `crossings()` + `two_consecutive_ge()` → 触发判定
4. **冷却过滤**: `in_cooldown()` → 去重复通知
5. **消息发送**: `send_telegram()` → Telegram Bot API
6. **状态保存**: `save_state()` → state.json

## 许可证

本项目基于MIT许可证开源。

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。

## 更新日志

- **v1.0.0**: 初始版本发布，包含完整的FGI监控和Telegram通知功能