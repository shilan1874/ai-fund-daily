import os
import time

import pandas as pd

from src.agents.data_agent import batch_get_stock_data, get_all_ashare_codes, get_financial_metrics
from src.agents.news_agent import get_market_overview


SCAN_TIME_BUDGET_SECONDS = int(os.getenv("SCAN_TIME_BUDGET_SECONDS", "240"))
ENABLE_FUNDAMENTAL_FILTER = os.getenv("ENABLE_FUNDAMENTAL_FILTER", "false").lower() == "true"
MAX_FUNDAMENTAL_CHECKS = int(os.getenv("MAX_FUNDAMENTAL_CHECKS", "20"))


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def _passes_liquidity_filter(df: pd.DataFrame) -> bool:
    if df is None or df.empty or len(df) < 60:
        return False

    if "amount" in df.columns:
        avg_amount = pd.to_numeric(df["amount"], errors="coerce").tail(20).mean() / 1e8
    else:
        avg_amount = (pd.to_numeric(df["volume"], errors="coerce") * pd.to_numeric(df["close"], errors="coerce")).tail(20).mean() / 1e8
    if avg_amount < 1.0:
        return False

    if "turnover_rate" in df.columns:
        turnover = pd.to_numeric(df["turnover_rate"], errors="coerce").tail(20).mean()
        if turnover and not 0.8 <= turnover <= 12.0:
            return False

    return True


def _tech_score_from_data(df: pd.DataFrame) -> int:
    try:
        df = df.tail(60)
        close = pd.to_numeric(df["close"], errors="coerce")
        volume = pd.to_numeric(df["volume"], errors="coerce")
        ma20 = close.rolling(20).mean().iloc[-1]
        price = close.iloc[-1]
        vol_now = volume.iloc[-1]
        vol_avg = volume.iloc[-20:].mean()
        vol_ratio = vol_now / vol_avg if vol_avg else 0

        score = 0
        if price > ma20:
            score += 30
        if vol_ratio > 1.2:
            score += 40
        if close.iloc[-1] > close.iloc[-5]:
            score += 30
        return score
    except Exception:
        return 0


def _passes_fundamental_filter(symbol: str) -> bool:
    fin_data = get_financial_metrics(symbol)
    if len(fin_data) < 3:
        return False

    profits = [_to_float(item.get("净利润(元)")) for item in fin_data]
    if not all(profit > 0 for profit in profits):
        return False

    roe_values = [_to_float(item.get("净资产收益率(%)")) for item in fin_data]
    if sum(roe_values) / len(roe_values) < 8:
        return False

    debt_values = [_to_float(item.get("资产负债率(%)")) for item in fin_data]
    if sum(debt_values) / len(debt_values) > 60:
        return False

    return True


def scan_top_stocks(top_num: int = 5) -> list[tuple[str, int]]:
    started_at = time.monotonic()
    codes = get_all_ashare_codes()
    stock_data = batch_get_stock_data(codes)
    scored: list[tuple[str, int]] = []

    for code, df in stock_data.items():
        if time.monotonic() - started_at > SCAN_TIME_BUDGET_SECONDS:
            print("扫描达到时间预算，提前结束。")
            break
        if not _passes_liquidity_filter(df):
            continue
        score = _tech_score_from_data(df)
        if score >= 60:
            scored.append((code, score))

    scored.sort(key=lambda item: item[1], reverse=True)

    if not ENABLE_FUNDAMENTAL_FILTER:
        return scored[:top_num]

    qualified: list[tuple[str, int]] = []
    for code, score in scored[:MAX_FUNDAMENTAL_CHECKS]:
        if time.monotonic() - started_at > SCAN_TIME_BUDGET_SECONDS:
            break
        if _passes_fundamental_filter(code):
            qualified.append((code, score))
        if len(qualified) >= top_num:
            break

    return qualified


def run_hedge_fund() -> str:
    market_info = get_market_overview()
    stock_list = scan_top_stocks(5)

    if not stock_list:
        return "今日候选池无符合【流动性安全+技术面强势】的标的，建议观望。"

    output = ""
    for code, score in stock_list:
        output += f"股票代码：{code} | 综合评分：{score}分（流动性与技术面强势）\n"

    fundamental_text = "已开启逐股财务过滤：连续盈利、ROE>8%、负债率<60%。" if ENABLE_FUNDAMENTAL_FILTER else "GitHub极速模式默认关闭逐股财务过滤，优先保证日报稳定运行。"

    return f"""
【市场环境筛查】
{market_info}

【AI对冲基金精选A股标的（极速扫描）】
{output}
筛选逻辑：
1. 候选池：按成交额、市值、非ST等条件快速预筛
2. 风控过滤：流动性充足、换手率不过热、K线数据完整
3. 技术面：20日线多头、放量启动、趋势向上
4. 基本面：{fundamental_text}
""".strip()
