# GitHub Actions 部署指南

## 🎯 部署概述

FGI监控系统现已准备好部署到GitHub Actions，支持以下功能：

### ✅ 核心功能
- **监控模式** - 每小时第7分钟自动检测FGI触发
- **定时汇报** - 每日早中晚三次汇报（北京时间08:30/12:30/20:30）
- **被动汇报** - 智能数据汇报（无触发时也会汇报）
- **状态管理** - 自动提交状态文件变更到仓库

### ❌ 已移除功能
- **Bot交互模式** - 因事件循环冲突问题已禁用

## 📋 部署前检查清单

### 1. 项目文件确认 ✅

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/fgi_notifier.py` | ✅ 完整 | 主程序，支持monitor/scheduled模式 |
| `src/config.py` | ✅ 完整 | 全部配置参数 |
| `src/report_generator.py` | ✅ 完整 | 统一汇报生成器 |
| `src/scheduled_reports.py` | ✅ 完整 | 定时汇报处理器 |
| `requirements.txt` | ✅ 完整 | Python依赖 |
| `.github/workflows/fgi-notify.yml` | ✅ 完整 | GitHub Actions工作流 |
| `state/state.json` | ✅ 完整 | 状态管理文件 |

### 2. Python环境配置 ✅

```yaml
# GitHub Actions 自动解决Python环境问题
- name: Setup Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.11"

- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
```

**优势**：
- 每次运行都是全新的Ubuntu环境
- Python 3.11 预装，无版本冲突
- pip自动安装所有依赖
- 无需手动配置虚拟环境

## 🔧 环境变量配置步骤

### 第一步：进入仓库设置

1. 访问你的GitHub仓库
2. 点击 **Settings** 标签
3. 在左侧菜单选择 **Secrets and variables** → **Actions**

### 第二步：添加必需的Secrets

点击 **New repository secret** 添加以下变量：

| Secret名称 | 值 | 说明 |
|------------|----|----- |
| `TELEGRAM_BOT_TOKEN` | `8420792636:AAH9bRcdzzt24huBYHs8lXGkC3TUiye-33Y` | 你的Bot Token |
| `TELEGRAM_CHAT_ID` | `123456789,5031618795` | 接收消息的Chat ID（支持多个，用逗号/分号/空白分隔）|

### 第三步：验证Secrets设置

设置完成后，在Secrets页面应该看到：
```
TELEGRAM_BOT_TOKEN ✓
TELEGRAM_CHAT_ID ✓
```

## 🚀 部署执行步骤

### 方法1：推送代码自动部署

1. **提交所有代码到仓库**：
   ```bash
   git add .
   git commit -m "feat: 完整FGI监控系统部署"
   git push origin main
   ```

2. **GitHub Actions自动触发**：
   - 推送后，定时任务会自动生效
   - 无需额外操作

### 方法2：手动触发测试

1. **进入GitHub仓库页面**
2. **点击 Actions 标签**
3. **选择 "FGI Monitoring System" 工作流**
4. **点击 "Run workflow"**
5. **选择运行模式**：
   - `monitor` - 测试监控功能
   - `scheduled` - 测试定时汇报

## 📅 自动运行时间表

部署成功后，系统按以下时间自动运行：

| 时间 | 模式 | 功能 |
|------|------|------|
| **每小时第7分钟** | monitor | 检测FGI触发 + 智能汇报 |
| **每日 00:30 UTC** | scheduled | 早报（北京08:30） |
| **每日 04:30 UTC** | scheduled | 午报（北京12:30） |
| **每日 12:30 UTC** | scheduled | 晚报（北京20:30） |

## 🔍 部署验证方法

### 1. 检查工作流状态
- 进入 **Actions** 页面
- 查看最近的运行记录
- 确认运行状态为 ✅ Success

### 2. 验证Telegram消息
- 检查Telegram是否收到测试消息
- 确认消息格式正确

### 3. 监控状态文件更新
- 查看仓库中 `state/state.json` 文件
- 确认 `last_processed_date` 正在更新

## ⚠️ 常见问题解决

### 问题1：工作流不运行
**原因**：环境变量未设置或仓库权限不足
**解决**：检查Secrets设置，确认Actions权限已启用

### 问题2：Python依赖安装失败
**原因**：`requirements.txt` 版本冲突
**解决**：当前版本已测试，通常不会出现此问题

### 问题3：Telegram消息发送失败
**原因**：Bot Token或Chat ID错误
**解决**：重新检查并更新Secrets中的值

### 问题4：状态文件提交失败
**原因**：GitHub权限不足
**解决**：工作流已配置 `contents: write` 权限，无需额外设置

## 🎉 部署成功标志

当你看到以下情况时，说明部署成功：

1. **GitHub Actions** ✅ 所有工作流运行成功
2. **Telegram消息** ✅ 收到系统汇报消息
3. **状态更新** ✅ `state.json` 文件定期更新
4. **定时任务** ✅ 早中晚定时汇报按时发送

## 🔄 后续维护

- **监控运行状态**：定期检查Actions页面
- **查看汇报内容**：通过Telegram接收数据
- **状态文件管理**：系统自动维护，无需手动操作
- **配置调整**：如需修改时间或阈值，编辑 `src/config.py`

---

## 📞 技术支持

如有部署问题：
1. 检查GitHub Actions运行日志
2. 验证Secrets配置
3. 确认Bot Token和Chat ID有效性

**🎯 关键提醒**：Bot交互模式已禁用，但所有核心监控功能完全正常！
