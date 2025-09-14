下面是“GitHub Actions + Python + Telegram”的全套搭建方案与执行标准。按此执行，能实现：24/7 定时拉取加密恐慌与贪婪指数(FGI)、计算7日均值FGI7、按你指定的阈值与7天冷却生成“卖出提醒”、通过Telegram通知你（仅提醒，你手动卖）。方案尽量避免返工：逻辑明确、状态持久化、测试可跑、部署可验证。



重要说明

\- 数据源：使用 alternative.me 的 Fear \& Greed Index API（稳定JSON接口）。不抓取网页，避免脆弱性。

\- 不做行情/K线：仅基于 FGI 与 FGI7；“价格保护”作为可选增强，默认关闭。

\- 运行环境：GitHub Actions 定时任务，免服务器、24/7、免费。状态持久化回仓库，保证幂等与去重。



一、策略与判定（最终版）

\- 指标：FGI7 = 最近7天的 FGI 简单平均（包含当天）。

\- 低于60：不卖（不触发）。

\- 上穿触发（分层减仓，且同一阈值7天内只触发一次）：

&nbsp; - FGI7 上穿 70：卖出10%仓位。

&nbsp; - FGI7 上穿 80：再卖15%。

&nbsp; - FGI7 上穿 90：再卖25%。

\- 90级额外触发（同属90桶，7天内只触发一次）：

&nbsp; - 若未发生“上穿90”，但最近连续2天 FGI7 ≥ 90，则触发90级卖出25%。

\- 上穿定义：昨日 FGI7 ≤ 阈值 且 今日 FGI7 > 阈值。

\- 跨级同日：若昨日≤70、今日>90，按 70 → 80 → 90 顺序依次触发（各自独立冷却）。

\- 冷却：每个阈值独立7天冷却；冷却内不重复触发同层次。

\- 初始化：首次上线当天不追溯过往，不产生“历史上穿”的补发；从上线后的新数据开始判断。



二、数据来源与刷新

\- API：GET https://api.alternative.me/fng/?limit=14\&format=json

&nbsp; - 返回字段 data\[].value, data\[].timestamp（UTC秒）。

&nbsp; - 我们按 timestamp 升序，计算最近7天与8天前的滑窗平均，得到今日/昨日 FGI7。

\- 刷新频率：每小时运行一次；FGI每日更新为主，但小时级运行可保证“第一时间”发现新日数据。

\- 无新数据：若最新日与上次相同日期，跳过（去重），不发消息。



三、状态持久化与去重

\- 文件：state/state.json（提交回仓库）

\- 内容：

&nbsp; - last\_processed\_date：上次处理的“FGI自然日”（YYYY-MM-DD）

&nbsp; - last\_trigger\_at：{ "70": "YYYY-MM-DD", "80": "YYYY-MM-DD", "90": "YYYY-MM-DD" }

&nbsp; - bootstrapped：true/false（首次上线不触发历史信号）

\- 去重规则：

&nbsp; - 同一自然日仅处理一次。

&nbsp; - 每个阈值7天冷却（以自然日为单位）。

&nbsp; - 90级“上穿”和“连续2天≥90”属于同一“90桶”，同一冷却。



四、通知渠道与格式

\- Telegram Bot：通过 HTTP POST 发送到 https://api.telegram.org/bot{TOKEN}/sendMessage

\- 必要Secret：

&nbsp; - TELEGRAM\_BOT\_TOKEN

&nbsp; - TELEGRAM\_CHAT\_ID

\- 消息模板（示例）：

&nbsp; \[卖出提醒] FGI7触发

&nbsp; 日期: 2025-09-14 (UTC)

&nbsp; 今日FGI7: 86.2 (昨日: 69.8)

&nbsp; 触发: 上穿70 → 卖出10%

&nbsp; 说明: 按分层规则执行；同层7天内不重复提醒

&nbsp; 数据源: alternative.me

&nbsp; 备注: 仅提醒，你手动执行卖出



\- 多级触发同日时，将在一条消息中按顺序列出多层触发（例如：上穿70→80→90 三层）。



五、仓库结构（建议）

\- README.md：部署说明与运行指引

\- requirements.txt：Python依赖（requests, pyyaml 可选）

\- src/

&nbsp; - fgi\_notifier.py：主逻辑（拉取→计算→判定→通知→持久化）

&nbsp; - state.py：状态读写、冷却校验

&nbsp; - notify.py：Telegram发送

&nbsp; - strategy.py：策略计算与触发生成

&nbsp; - config.py：常量、阈值、冷却天数、运行模式

\- state/

&nbsp; - state.json：运行态（Actions提交回仓库）

\- .github/workflows/

&nbsp; - fgi-notify.yml：定时工作流（含依赖安装、运行、状态回写）



六、核心代码（可直接使用）



requirements.txt

requests==2.32.3

pyyaml==6.0.2



src/config.py

FGI\_API = "https://api.alternative.me/fng/?limit=14\&format=json"

THRESHOLDS = \[70, 80, 90]  # 顺序重要

SELL\_MAP = {70: 10, 80: 15, 90: 25}  # 百分比

COOLDOWN\_DAYS = 7

MIN\_SELL\_LEVEL = 60  # 低于60不卖，仅描述用

TIMEZONE = "UTC"  # 状态日期用UTC自然日

BOOTSTRAP\_SUPPRESS\_FIRST\_DAY = True  # 上线首日不触发历史信号



src/state.py

import json, os, datetime as dt



STATE\_DIR = "state"

STATE\_FILE = os.path.join(STATE\_DIR, "state.json")

DATE\_FMT = "%Y-%m-%d"



DEFAULT\_STATE = {

&nbsp;   "last\_processed\_date": None,

&nbsp;   "last\_trigger\_at": {"70": None, "80": None, "90": None},

&nbsp;   "bootstrapped": False

}



def load\_state():

&nbsp;   if not os.path.exists(STATE\_FILE):

&nbsp;       os.makedirs(STATE\_DIR, exist\_ok=True)

&nbsp;       save\_state(DEFAULT\_STATE.copy())

&nbsp;   with open(STATE\_FILE, "r", encoding="utf-8") as f:

&nbsp;       return json.load(f)



def save\_state(state):

&nbsp;   os.makedirs(STATE\_DIR, exist\_ok=True)

&nbsp;   with open(STATE\_FILE, "w", encoding="utf-8") as f:

&nbsp;       json.dump(state, f, ensure\_ascii=False, indent=2)



def days\_since(date\_str, today):

&nbsp;   if not date\_str:

&nbsp;       return None

&nbsp;   d = dt.datetime.strptime(date\_str, DATE\_FMT).date()

&nbsp;   return (today - d).days



def today\_utc\_date():

&nbsp;   return dt.datetime.utcnow().date()



def in\_cooldown(state, level, today):

&nbsp;   last = state\["last\_trigger\_at"].get(str(level))

&nbsp;   if not last:

&nbsp;       return False

&nbsp;   since = days\_since(last, today)

&nbsp;   return since is not None and since < 7



def mark\_trigger(state, level, today):

&nbsp;   state\["last\_trigger\_at"]\[str(level)] = today.strftime(DATE\_FMT)



def mark\_processed(state, date\_obj):

&nbsp;   state\["last\_processed\_date"] = date\_obj.strftime(DATE\_FMT)



def bootstrapped(state):

&nbsp;   return state.get("bootstrapped", False)



def set\_bootstrapped(state):

&nbsp;   state\["bootstrapped"] = True



src/notify.py

import os, requests



TG\_TOKEN = os.getenv("TELEGRAM\_BOT\_TOKEN")

TG\_CHAT = os.getenv("TELEGRAM\_CHAT\_ID")



def send\_telegram(text):

&nbsp;   if not TG\_TOKEN or not TG\_CHAT:

&nbsp;       print("Telegram not configured; printing message:\\n", text)

&nbsp;       return

&nbsp;   url = f"https://api.telegram.org/bot{TG\_TOKEN}/sendMessage"

&nbsp;   payload = {"chat\_id": TG\_CHAT, "text": text}

&nbsp;   r = requests.post(url, json=payload, timeout=15)

&nbsp;   r.raise\_for\_status()

&nbsp;   return r.json()



src/strategy.py

from statistics import mean



def compute\_fgi7(values\_desc):

&nbsp;   # values\_desc: \[(date, value\_int)] 按日期升序列表

&nbsp;   # 返回 (fgi7\_prev, fgi7\_today)

&nbsp;   if len(values\_desc) < 8:

&nbsp;       return None, None

&nbsp;   vals = \[v for (\_, v) in values\_desc]

&nbsp;   fgi7\_today = round(mean(vals\[-7:]), 2)

&nbsp;   fgi7\_prev = round(mean(vals\[-8:-1]), 2)

&nbsp;   return fgi7\_prev, fgi7\_today



def two\_consecutive\_ge(values\_desc, thresh=90):

&nbsp;   # 是否最近连续2天 FGI7 >= thresh

&nbsp;   if len(values\_desc) < 7 + 2:

&nbsp;       return False

&nbsp;   # 先构造逐日的FGI7序列，取最后两天

&nbsp;   fgi7\_series = \[]

&nbsp;   for i in range(6, len(values\_desc)):

&nbsp;       window = \[v for (\_, v) in values\_desc\[i-6:i+1]]

&nbsp;       fgi7\_series.append(round(mean(window), 2))

&nbsp;   return len(fgi7\_series) >= 2 and fgi7\_series\[-1] >= thresh and fgi7\_series\[-2] >= thresh



def crossings(prev, today, thresholds):

&nbsp;   # 计算从 prev -> today 上穿的阈值（按顺序）

&nbsp;   fired = \[]

&nbsp;   for t in thresholds:

&nbsp;       if prev is not None and prev <= t and today is not None and today > t:

&nbsp;           fired.append(t)

&nbsp;   return fired



src/fgi\_notifier.py

import os, sys, requests, datetime as dt

from statistics import mean

from src.config import FGI\_API, THRESHOLDS, SELL\_MAP, COOLDOWN\_DAYS, BOOTSTRAP\_SUPPRESS\_FIRST\_DAY

from src.state import load\_state, save\_state, today\_utc\_date, in\_cooldown, mark\_trigger, mark\_processed, bootstrapped, set\_bootstrapped

from src.notify import send\_telegram

from src.strategy import compute\_fgi7, two\_consecutive\_ge, crossings



def fetch\_fgi():

&nbsp;   r = requests.get(FGI\_API, timeout=20)

&nbsp;   r.raise\_for\_status()

&nbsp;   data = r.json()\["data"]

&nbsp;   # API返回常见为倒序；统一为按日期升序

&nbsp;   items = \[]

&nbsp;   for d in data:

&nbsp;       ts = int(d\["timestamp"])

&nbsp;       day = dt.datetime.utcfromtimestamp(ts).date()

&nbsp;       val = int(d\["value"])

&nbsp;       items.append((day, val))

&nbsp;   items.sort(key=lambda x: x\[0])

&nbsp;   # 去重: 同日多条保留最后一条（理论不会发生）

&nbsp;   dedup = {}

&nbsp;   for day, val in items:

&nbsp;       dedup\[day] = val

&nbsp;   out = sorted(dedup.items(), key=lambda x: x\[0])  # \[(date, val)]

&nbsp;   return out



def main():

&nbsp;   state = load\_state()

&nbsp;   values = fetch\_fgi()

&nbsp;   if len(values) < 8:

&nbsp;       print("Insufficient FGI history; need >= 8 days.")

&nbsp;       return 0



&nbsp;   # 今日自然日（按FGI数据最后一天）

&nbsp;   latest\_day, latest\_val = values\[-1]

&nbsp;   prev7, today7 = compute\_fgi7(values)

&nbsp;   if prev7 is None:

&nbsp;       print("Not enough data for FGI7.")

&nbsp;       return 0



&nbsp;   # 首次上线：记录状态，不触发历史信号

&nbsp;   if BOOTSTRAP\_SUPPRESS\_FIRST\_DAY and not bootstrapped(state):

&nbsp;       set\_bootstrapped(state)

&nbsp;       mark\_processed(state, latest\_day)

&nbsp;       save\_state(state)

&nbsp;       send\_telegram(f"\[初始化] 已上线并开始跟踪 FGI\\n最近日期: {latest\_day} FGI={latest\_val} FGI7={today7}")

&nbsp;       print("Bootstrapped. No historical firing.")

&nbsp;       return 0



&nbsp;   # 无新日数据则跳过

&nbsp;   last\_proc = state.get("last\_processed\_date")

&nbsp;   if last\_proc:

&nbsp;       last\_proc\_date = dt.datetime.strptime(last\_proc, "%Y-%m-%d").date()

&nbsp;       if latest\_day <= last\_proc\_date:

&nbsp;           print(f"No new day. latest={latest\_day}, last\_processed={last\_proc\_date}")

&nbsp;           return 0



&nbsp;   # 核心策略判定

&nbsp;   fired\_levels = \[]



&nbsp;   # 1) 上穿判定（70->80->90顺序，允许同日多级）

&nbsp;   ups = crossings(prev7, today7, THRESHOLDS)

&nbsp;   fired\_levels.extend(ups)



&nbsp;   # 2) 连续两日 >=90 的 90桶判定（若未因上穿已触发）

&nbsp;   if 90 not in ups and two\_consecutive\_ge(values, 90):

&nbsp;       fired\_levels.append(90)



&nbsp;   # 3) 低于60不卖：非硬条件，仅提示；不会清除已触发层的冷却

&nbsp;   below\_60\_note = today7 < 60



&nbsp;   # 冷却过滤

&nbsp;   today = latest\_day

&nbsp;   final\_levels = \[]

&nbsp;   for t in fired\_levels:

&nbsp;       if not in\_cooldown(state, t, today):

&nbsp;           final\_levels.append(t)



&nbsp;   # 组装消息

&nbsp;   lines = \[]

&nbsp;   lines.append("\[卖出提醒] FGI7触发")

&nbsp;   lines.append(f"日期: {today} (UTC)")

&nbsp;   lines.append(f"今日FGI7: {today7} (昨日: {prev7})，今日FGI: {latest\_val}")

&nbsp;   if final\_levels:

&nbsp;       actions = \[]

&nbsp;       for t in final\_levels:

&nbsp;           pct = SELL\_MAP\[t]

&nbsp;           actions.append(f"上穿{t} → 卖出{pct}%")

&nbsp;       lines.append("触发: " + "；".join(actions))

&nbsp;   else:

&nbsp;       if fired\_levels:

&nbsp;           lines.append("触发: 有信号但处于冷却期，未提醒新卖出")

&nbsp;       else:

&nbsp;           lines.append("触发: 无")

&nbsp;   if today7 < 60:

&nbsp;       lines.append("说明: FGI7<60（不卖，仅提示）")

&nbsp;   lines.append("规则: 同一阈值7天内只执行一次；跨级同日依序触发")

&nbsp;   lines.append("数据源: alternative.me")

&nbsp;   message = "\\n".join(lines)



&nbsp;   # 若有最终触发层则通知；若无触发但你想每日播报，可加开关

&nbsp;   if final\_levels:

&nbsp;       send\_telegram(message)

&nbsp;       for t in final\_levels:

&nbsp;           mark\_trigger(state, t, today)

&nbsp;   else:

&nbsp;       print("No final actions to notify.")



&nbsp;   # 更新处理标记与持久化

&nbsp;   mark\_processed(state, today)

&nbsp;   save\_state(state)

&nbsp;   print("Done.")

&nbsp;   return 0



if \_\_name\_\_ == "\_\_main\_\_":

&nbsp;   sys.exit(main())



.github/workflows/fgi-notify.yml

name: FGI Notifier



on:

&nbsp; schedule:

&nbsp;   - cron: "7 \* \* \* \*"  # 每小时第7分钟运行，错峰

&nbsp; workflow\_dispatch:



permissions:

&nbsp; contents: write  # 允许提交state.json

&nbsp; actions: read



concurrency:

&nbsp; group: fgi-notifier

&nbsp; cancel-in-progress: false



jobs:

&nbsp; run:

&nbsp;   runs-on: ubuntu-latest

&nbsp;   steps:

&nbsp;     - name: Checkout

&nbsp;       uses: actions/checkout@v4

&nbsp;       with:

&nbsp;         fetch-depth: 0



&nbsp;     - name: Setup Python

&nbsp;       uses: actions/setup-python@v5

&nbsp;       with:

&nbsp;         python-version: "3.11"



&nbsp;     - name: Install deps

&nbsp;       run: |

&nbsp;         python -m pip install --upgrade pip

&nbsp;         pip install -r requirements.txt



&nbsp;     - name: Run notifier

&nbsp;       env:

&nbsp;         TELEGRAM\_BOT\_TOKEN: ${{ secrets.TELEGRAM\_BOT\_TOKEN }}

&nbsp;         TELEGRAM\_CHAT\_ID: ${{ secrets.TELEGRAM\_CHAT\_ID }}

&nbsp;       run: |

&nbsp;         python -m src.fgi\_notifier



&nbsp;     - name: Commit state if changed

&nbsp;       run: |

&nbsp;         if \[\[ -n "$(git status --porcelain state/state.json 2>/dev/null)" ]]; then

&nbsp;           git config user.name "github-actions\[bot]"

&nbsp;           git config user.email "41898282+github-actions\[bot]@users.noreply.github.com"

&nbsp;           git add state/state.json

&nbsp;           git commit -m "chore(state): update on $(date -u +'%Y-%m-%dT%H:%M:%SZ')"

&nbsp;           git push

&nbsp;         else

&nbsp;           echo "No state change."



七、部署步骤（一步步）

\- 创建私有仓库，拉取本答案内文件到你的仓库（保持路径一致）。

\- 在 GitHub 仓库设置 → Secrets and variables → Actions → New repository secret：

&nbsp; - TELEGRAM\_BOT\_TOKEN：从 @BotFather 获取

&nbsp; - TELEGRAM\_CHAT\_ID：给你的Bot发一条消息，用 getUpdates 或 @userinfobot 获取 chat id

\- 可选：编辑 src/config.py 调整阈值、冷却天数、首日抑制开关。

\- 提交代码到主分支，Actions 会按计划运行；也可在 Actions 页面手动触发 workflow\_dispatch。

\- 首次运行：

&nbsp; - 会发送一次“初始化”消息（不触发卖出）。

&nbsp; - state/state.json 会被写入并提交。

\- 次日/有新日数据时：

&nbsp; - 若触发条件命中，Telegram 会收到“卖出提醒”（包含层级与比例）。



八、验证与测试

\- 本地干跑（可选）：

&nbsp; - 配置环境变量后：`python -m src.fgi\_notifier`

&nbsp; - 首次将生成 state/state.json，并打印/发送初始化信息。

\- 触发测试（人工模拟）：

&nbsp; - 临时修改 src/state.py 中的 `mark\_processed` 前后，或直接手动把 state/state.json 的 last\_processed\_date 回退一天并将 last\_trigger\_at 清空，再次运行，观察是否根据当前 FGI7 上穿情况发送提醒。

\- 逻辑单测（轻量）：

&nbsp; - 将 src/strategy.py 的 compute\_fgi7 与 crossings 用固定数组检查：

&nbsp;   - 例：prev7=69.9, today7=70.1 → crossings 返回 \[70]

&nbsp;   - 例：prev7=79.5, today7=90.3 → crossings 返回 \[80,90]

&nbsp;   - 例：prev7=90.2, today7=90.1 → crossings 返回 \[]，但 two\_consecutive\_ge 可能为 True → 触发90桶

\- Actions 日志检查：

&nbsp; - “Run notifier” 步会打印今日/昨日FGI7与是否有触发。

&nbsp; - “Commit state if changed” 步显示是否提交 state。



九、运行与维护标准

\- 幂等：同一自然日仅处理一次；冷却内不重复提醒；多级同日顺序触发。

\- 可观测性：错误会在 Actions 日志中显示；可在失败时添加一个“错误Telegram通知”的增强步骤。

\- 变更：

&nbsp; - 改阈值/冷却：调 src/config.py；上线后从新数据生效。

&nbsp; - 清空冷却：删除或编辑 state/state.json 的 last\_trigger\_at；提交后生效。

&nbsp; - 迁移仓库：拷贝整个项目含 state/ 目录，保留历史冷却状态。

\- 安全：Telegram Token 放 Secrets；仓库建议私有；state.json 不含敏感信息，仅日期。



十、可选增强（按需开启）

\- 每日播报：即使无触发也发送当日 FGI 与 FGI7 概览（加开关）。

\- 价格保护（需要价格源，默认开启）：

&nbsp; - 逻辑：当90级触发后，记录“保护已开启”；随后若 BTCUSDT 自触发后最高价回撤≥8%，则发送“保护提醒”。

&nbsp; - 数据：拉取币安 ticker 即可（无需K线）；实现上增加 src/price\_guard.py 与配置。

\- 备用渠道：并发飞书/钉钉/邮件；notify.py 增加多适配器。

\- 频率：若想更快，可改 cron 为每15分钟；不建议低于10分钟，API更新仍以日为主。



十一、交付验收清单

\- 能力：在新日数据产生当天，按策略（70/80/90+7天冷却）推送Telegram卖出提醒。

\- 去重：同层7天内不重复；同日多级顺序触发；无新日数据不动作。

\- 状态：state/state.json 正常更新并提交；包含 last\_processed\_date 与 last\_trigger\_at。

\- 稳定：错误零退出；无网络/API错误时不中断后续运行；超时具备失败日志。

\- 文档：README 说明完备；Secrets 已配置；手动触发可用。



十二、README 草案（可放仓库根）

项目简介

\- GitHub Actions 定时拉取加密恐慌与贪婪指数，按预设策略计算卖出提醒，通过 Telegram 通知。



部署步骤

\- 填入 Telegram Secrets（TELEGRAM\_BOT\_TOKEN、TELEGRAM\_CHAT\_ID）

\- 可选编辑 src/config.py

\- 推送代码 → Actions 自动运行；手动“Run workflow”可立即测试

\- 收到初始化消息后，等待新日数据触发提醒



策略说明

\- 低于60不卖

\- FGI7 上穿70/80/90 分别提示卖出 10%/15%/25%

\- 连续两天 FGI7≥90 亦触发90层

\- 同层7天内只触发一次；跨级同日依序触发

\- 首次上线不追溯历史，不补发



运维

\- 查看 Actions 日志与 state/state.json

\- 修改阈值或冷却后推送代码

\- 如需清空冷却，编辑 state/state.json 的 last\_trigger\_at



问题排查

\- 未收到消息：检查 Telegram Secrets、Actions 日志中 sendMessage 返回

\- 状态不更新：检查“Commit state if changed”步骤是否有提交

\- 无触发：查看日志中的 FGI7 与 crossings 结果



需要你确认的点

\- 是否采用“首次上线不触发历史”的策略（已默认开启，可切换）。

\- “连续2天≥90”使用 FGI7 还是原始 FGI 值（当前用 FGI7，抗噪更稳）。

\- 是否开启“每日播报”与“价格保护”增强（默认开启）。

