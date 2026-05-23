from typing import Any
import time

import akshare as ak
import pandas as pd


FALLBACK_A_SHARE_CODES = [
    "000001",
    "000002",
    "000063",
    "000333",
    "000538",
    "000568",
    "000651",
    "000858",
    "002027",
    "002142",
    "002230",
    "002271",
    "002415",
    "002594",
    "002714",
    "300015",
    "300059",
    "300124",
    "300274",
    "300308",
    "300750",
    "600000",
    "600009",
    "600030",
    "600031",
    "600036",
    "600048",
    "600050",
    "600104",
    "600276",
    "600309",
    "600519",
    "600585",
    "600690",
    "600887",
    "601012",
    "601088",
    "601166",
    "601318",
    "601398",
    "601628",
    "601668",
    "601688",
    "601888",
    "603259",
    "603288",
    "603501",
]


def _with_retries(func, *args, retries: int = 3, delay: float = 2.0, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    raise last_exc


def get_stock_data(ticker: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """Fetch A-share daily K-line data in the original project's common shape."""
    df = _with_retries(ak.stock_zh_a_hist, symbol=ticker, period="daily", start_date=start_date or "19900101", end_date=end_date or "20500101", adjust="qfq")
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
    info_df = _with_retries(ak.stock_individual_info_em, symbol=ticker)
    return dict(zip(info_df["item"], info_df["value"], strict=False))


def get_financial_metrics(ticker: str) -> list[dict[str, Any]]:
    fin_df = _with_retries(ak.stock_financial_analysis_indicator, symbol=ticker).tail(3)
    return fin_df.to_dict("records")


def get_all_ashare_codes() -> list[str]:
    try:
        df = _with_retries(ak.stock_info_a_code_name)
        return df["code"].astype(str).str.zfill(6).tolist()
    except Exception as primary_exc:
        print(f"获取 A 股代码列表主接口失败，切换备用接口：{primary_exc}")

    try:
        df = _with_retries(ak.stock_zh_a_spot_em)
        code_col = "代码" if "代码" in df.columns else "code"
        return df[code_col].astype(str).str.zfill(6).tolist()
    except Exception as fallback_exc:
        print(f"获取 A 股代码列表备用接口失败，使用内置核心股票池：{fallback_exc}")
        return FALLBACK_A_SHARE_CODES
