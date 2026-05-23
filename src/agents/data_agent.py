import akshare as ak
import pandas as pd
import time
from functools import wraps
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# 终极提速配置（专治GitHub海外慢网络、串行卡死）
MAX_RETRY = 2
REQ_DELAY = 0.3
# 并行线程数，既快又不被风控
THREAD_WORKERS = 30

# 轻量化重试装饰器
def retry(max_tries=MAX_RETRY, delay=REQ_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tries = 0
            while tries < max_tries:
                try:
                    res = func(*args, **kwargs)
                    # 兜底：空数据直接重试
                    if res is None or (isinstance(res, list) and len(res) == 0):
                        raise ValueError("empty data")
                    return res
                except Exception:
                    tries += 1
                    if tries == max_tries:
                        # 最终失败返回空列表，不返回None！解决None迭代报错
                        return []
                    time.sleep(delay)
            return []
        return wrapper
    return decorator

# 极速筛选有效A股标的
@retry()
def get_valid_ashare_codes() -> List[str]:
    df_all = ak.stock_info_a_code_name()
    # 兜底判断接口空数据
    if df_all is None or df_all.empty:
        return []
    # 剔除ST、北交所、垃圾股
    df_all = df_all[~df_all["name"].str.contains("ST", na=False)]
    df_all = df_all[df_all["code"].str.len() == 6]
    df_all = df_all[~df_all["code"].str.startswith("8")]
    # 只留主板6开头优质标的，剔除创业/科创
    valid_codes = [c for c in df_all["code"].tolist() if c.startswith("6")]
    # 限制最大数量，兜底防超时
    if len(valid_codes) > 600:
        valid_codes = valid_codes[:600]
    return valid_codes

# 完整字段K线数据获取（完全保留你所有字段）
@retry()
def get_stock_data(ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    try:
        df = ak.stock_zh_a_hist(symbol=ticker, period="daily", adjust="qfq", timeout=8)
        if df.empty or len(df) < 20:
            return None
        # 完整保留全部原始字段，无任何删减
        df = df.rename(columns={
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
            "换手率": "turnover_rate"
        })
        df["ticker"] = ticker
        return df
    except Exception:
        return None

@retry()
def get_stock_info(ticker: str) -> Optional[Dict]:
    try:
        info_df = ak.stock_individual_info_em(symbol=ticker)
        return dict(zip(info_df["item"], info_df["value"]))
    except:
        return None

@retry()
def get_financial_metrics(ticker: str):
    try:
        fin_df = ak.stock_financial_analysis_indicator(symbol=ticker).tail(3)
        return fin_df.to_dict("records")
    except:
        return None

# ========== 核心终极优化：并行批量获取数据 ==========
def batch_get_stock_data(codes: List[str]) -> List[pd.DataFrame]:
    """多线程并行拉取数据，彻底告别串行慢速卡死"""
    results = []
    if not codes:
        return results
    with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
        future_map = {executor.submit(get_stock_data, code): code for code in codes}
        for future in as_completed(future_map):
            res = future.result()
            if res is not None:
                results.append(res)
    return results

# 兼容旧项目全局接口，【关键修复】永远返回列表，绝不返回None
get_all_ashare_codes = get_valid_ashare_codes
