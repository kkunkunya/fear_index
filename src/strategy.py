# FGI恐慌贪婪指数监控项目 - 策略计算模块
# 负责FGI7滑动平均计算、上穿检测、连续检测等核心策略逻辑

from statistics import mean


def compute_fgi7(values_desc):
    """
    计算FGI7滑动平均值 - 核心策略指标

    FGI7是7天滑动平均值，比原始FGI更平滑，减少短期噪音
    用于判断市场趋势方向和触发卖出信号

    算法说明:
    - 需要至少8天历史数据才能计算昨日和今日的FGI7
    - 今日FGI7 = 最近7天FGI的算术平均值（包含今日）
    - 昨日FGI7 = 前7天FGI的算术平均值（不包含今日）
    - 两值比较用于判断是否发生"上穿"事件

    参数:
        values_desc: [(date, value_int)] 按日期升序的FGI数据列表
                    确保数据已按时间正序排列

    返回:
        tuple: (fgi7_prev, fgi7_today) 或 (None, None)
            - fgi7_prev: 昨日FGI7值，保留2位小数
            - fgi7_today: 今日FGI7值，保留2位小数
            - 数据不足时返回 (None, None)
    """
    # 需要至少8天数据：7天计算今日FGI7 + 1天计算昨日FGI7
    if len(values_desc) < 8:
        return None, None

    # 提取数值部分，忽略日期
    vals = [v for (_, v) in values_desc]

    # 今日FGI7：最近7天平均（包含今天）
    fgi7_today = round(mean(vals[-7:]), 2)

    # 昨日FGI7：前7天平均（不包含今天）
    fgi7_prev = round(mean(vals[-8:-1]), 2)

    return fgi7_prev, fgi7_today


def two_consecutive_ge(values_desc, thresh=90):
    """
    检测是否最近连续2天FGI7 >= 阈值

    参数:
        values_desc: [(date, value_int)] 按日期升序列表
        thresh: 阈值，默认90

    返回:
        bool - 是否连续2天满足条件
    """
    # 需要至少9天数据：7天计算第一个FGI7 + 2天计算连续两个FGI7
    if len(values_desc) < 7 + 2:
        return False

    # 构造逐日的FGI7序列
    fgi7_series = []
    for i in range(6, len(values_desc)):
        # 每个FGI7是当天及之前6天的7天平均
        window = [v for (_, v) in values_desc[i - 6 : i + 1]]
        fgi7_series.append(round(mean(window), 2))

    # 检查最后两天是否都 >= 阈值
    return (
        len(fgi7_series) >= 2
        and fgi7_series[-1] >= thresh
        and fgi7_series[-2] >= thresh
    )


def crossings(prev, today, thresholds):
    """
    计算从昨日到今日上穿的阈值列表

    参数:
        prev: 昨日FGI7值
        today: 今日FGI7值
        thresholds: 阈值列表，按顺序处理

    返回:
        list - 上穿的阈值列表（可能多个，用于跨级同日触发）
    """
    fired = []
    for t in thresholds:
        # 上穿定义：昨日 <= 阈值 且 今日 > 阈值
        if prev is not None and prev <= t and today is not None and today > t:
            fired.append(t)
    return fired
