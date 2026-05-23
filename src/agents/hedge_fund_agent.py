from src.agents.data_agent import get_all_ashare_codes, get_financial_metrics, get_stock_data, get_stock_info
from src.agents.news_agent import get_market_overview


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def is_qualified_stock(symbol: str) -> bool:
    """Filter risky, illiquid, or weak-fundamental A-share stocks."""
    try:
        info = get_stock_info(symbol)
        name = str(info.get("股票简称", ""))
        total_cap = _to_float(info.get("总市值")) / 1e8
        listed_days = int(_to_float(info.get("上市天数"), 9999))

        if "ST" in name:
            return False
        if listed_days < 365:
            return False
        if not 80 <= total_cap <= 1200:
            return False

        df = get_stock_data(symbol)
        if len(df) < 60:
            return False

        amount_col = "amount" if "amount" in df.columns else None
        avg_amount = df[amount_col].tail(20).mean() / 1e8 if amount_col else (df["volume"] * df["close"]).tail(20).mean() / 1e8
        if avg_amount < 1.5:
            return False

        turnover = df["turnover_rate"].tail(20).mean() if "turnover_rate" in df.columns else 3.0
        if not 2.0 <= turnover <= 8.0:
            return False

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
    except Exception:
        return False


def tech_score(symbol: str) -> int:
    """Score a stock by simple trend and volume breakout signals."""
    try:
        df = get_stock_data(symbol).tail(60)
        close = df["close"]
        ma20 = close.rolling(20).mean().iloc[-1]
        price = close.iloc[-1]
        vol_now = df["volume"].iloc[-1]
        vol_avg = df["volume"].iloc[-20:].mean()
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


def scan_top_stocks(top_num: int = 5) -> list[tuple[str, int]]:
    qualified: list[tuple[str, int]] = []
    for code in get_all_ashare_codes():
        if is_qualified_stock(code):
            score = tech_score(code)
            if score >= 60:
                qualified.append((code, score))

    qualified.sort(key=lambda item: item[1], reverse=True)
    return qualified[:top_num]


def run_hedge_fund() -> str:
    market_info = get_market_overview()
    stock_list = scan_top_stocks(5)

    if not stock_list:
        return "今日全市场无符合【基本面优质+技术面强势+流动性安全】标的，建议观望。"

    output = ""
    for code, score in stock_list:
        output += f"股票代码：{code} | 综合评分：{score}分（优质强势标的）\n"

    return f"""
【市场环境筛查】
{market_info}

【AI对冲基金精选A股标的（全市场扫描）】
{output}
筛选逻辑：
1. 基本面：连续盈利、ROE>8%、负债率<60%
2. 风控过滤：非ST、非次新、流动性充足、无僵尸垃圾股
3. 技术面：20日线多头、放量启动、趋势向上
""".strip()
