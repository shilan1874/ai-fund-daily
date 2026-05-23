from typing import Any

import akshare as ak
import pandas as pd


def get_stock_data(ticker: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """Fetch A-share daily K-line data in the original project's common shape."""
    df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start_date or "19900101", end_date=end_date or "20500101", adjust="qfq")
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
    info_df = ak.stock_individual_info_em(symbol=ticker)
    return dict(zip(info_df["item"], info_df["value"], strict=False))


def get_financial_metrics(ticker: str) -> list[dict[str, Any]]:
    fin_df = ak.stock_financial_analysis_indicator(symbol=ticker).tail(3)
    return fin_df.to_dict("records")


def get_all_ashare_codes() -> list[str]:
    df = ak.stock_info_a_code_name()
    return df["code"].astype(str).str.zfill(6).tolist()
