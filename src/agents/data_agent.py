import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd


MAX_RETRY = int(os.getenv("AKSHARE_MAX_RETRY", "2"))
REQ_DELAY = float(os.getenv("AKSHARE_RETRY_DELAY", "0.5"))
THREAD_WORKERS = int(os.getenv("THREAD_WORKERS", "8"))
DEFAULT_SCAN_LIMIT = int(os.getenv("MAX_SCAN_CODES", "30"))
USE_CORE_POOL = os.getenv("USE_CORE_POOL", "false").lower() == "true"

FALLBACK_A_SHARE_CODES = [
    "600519",
    "601318",
    "600036",
    "600276",
    "600309",
    "600887",
    "601166",
    "601398",
    "600030",
    "600031",
    "601888",
    "600690",
    "601012",
    "000001",
    "000333",
    "000651",
    "000858",
    "002415",
    "002594",
    "300750",
]


def _retry_call(func, *args, default=None, retries: int = MAX_RETRY, delay: float = REQ_DELAY, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    print(f"{func.__name__} 调用失败：{last_exc}")
    return default


def _as_code_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.extract(r"(\d{6})", expand=False).str.zfill(6)


def get_stock_data(ticker: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """Fetch recent A-share daily K-line data in a normalized shape."""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=220)).strftime("%Y%m%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    df = _retry_call(
        ak.stock_zh_a_hist,
        symbol=ticker,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
        timeout=8,
        default=pd.DataFrame(),
    )
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover_rate",
        }
    )
    df["ticker"] = ticker
    return df


def get_stock_info(ticker: str) -> dict[str, Any]:
    info_df = _retry_call(ak.stock_individual_info_em, symbol=ticker, default=pd.DataFrame())
    if info_df is None or info_df.empty:
        return {}
    return dict(zip(info_df["item"], info_df["value"], strict=False))


def get_financial_metrics(ticker: str) -> list[dict[str, Any]]:
    fin_df = _retry_call(ak.stock_financial_analysis_indicator, symbol=ticker, default=pd.DataFrame())
    if fin_df is None or fin_df.empty:
        return []
    return fin_df.tail(3).to_dict("records")


def get_all_ashare_codes(limit: int | None = None) -> list[str]:
    """Return a small, liquid candidate pool to keep GitHub Actions fast."""
    scan_limit = limit or DEFAULT_SCAN_LIMIT

    if USE_CORE_POOL:
        print(f"使用内置核心股票池：{min(scan_limit, len(FALLBACK_A_SHARE_CODES))} 只")
        return FALLBACK_A_SHARE_CODES[:scan_limit]

    spot_df = _retry_call(ak.stock_zh_a_spot_em, default=pd.DataFrame())
    if spot_df is not None and not spot_df.empty:
        code_col = "代码" if "代码" in spot_df.columns else "code"
        name_col = "名称" if "名称" in spot_df.columns else "name"
        amount_col = "成交额" if "成交额" in spot_df.columns else None
        cap_col = "总市值" if "总市值" in spot_df.columns else None

        df = spot_df.copy()
        df["code"] = _as_code_series(df[code_col])
        df["name"] = df[name_col].astype(str)
        df = df[df["code"].str.len() == 6]
        df = df[~df["code"].str.startswith("8")]
        df = df[~df["name"].str.contains("ST", na=False)]

        if amount_col:
            df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
            df = df[df[amount_col] >= 100_000_000]
            df = df.sort_values(amount_col, ascending=False)
        if cap_col:
            df[cap_col] = pd.to_numeric(df[cap_col], errors="coerce").fillna(0)
            df = df[(df[cap_col] >= 8_000_000_000) & (df[cap_col] <= 120_000_000_000)]

        codes = df["code"].dropna().drop_duplicates().head(scan_limit).tolist()
        if codes:
            print(f"候选股票池：{len(codes)} 只")
            return codes

    name_df = _retry_call(ak.stock_info_a_code_name, default=pd.DataFrame())
    if name_df is not None and not name_df.empty:
        codes = _as_code_series(name_df["code"]).dropna().drop_duplicates().head(scan_limit).tolist()
        if codes:
            print(f"候选股票池备用接口：{len(codes)} 只")
            return codes

    print("候选股票池接口不可用，使用内置核心股票池")
    return FALLBACK_A_SHARE_CODES[:scan_limit]


def batch_get_stock_data(codes: list[str]) -> dict[str, pd.DataFrame]:
    """Fetch K-line data concurrently with bounded workers."""
    results: dict[str, pd.DataFrame] = {}
    if not codes:
        return results

    with ThreadPoolExecutor(max_workers=max(1, THREAD_WORKERS)) as executor:
        future_map = {executor.submit(get_stock_data, code): code for code in codes}
        for future in as_completed(future_map):
            code = future_map[future]
            try:
                df = future.result()
            except Exception as exc:
                print(f"{code} K线获取失败：{exc}")
                continue
            if df is not None and not df.empty:
                results[code] = df
    return results
