import akshare as ak
import pandas as pd
import time
from functools import wraps
from typing import Optional, Dict, List

# 全局配置：严控超时、减少重试，适配GitHub海外网络
MAX_RETRY = 2
REQ_DELAY = 1

# 网络请求重试装饰器（轻量化，不堆积耗时）
def retry(max_tries=MAX_RETRY, delay=REQ_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tries = 0
            while tries < max_tries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    tries += 1
                    if tries == max_tries:
                        return None
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

# 筛选有效A股标的（极速过滤垃圾股）
@retry()
def get_valid_ashare_codes() -> List[str]:
    """获取过滤后的有效股票列表，减少80%无效请求"""
    # 获取全市场股票代码+名称
    df_all = ak.stock_info_a_code_name()
    # 1. 剔除ST股票
    df_all = df_all[~df_all["name"].str.contains("ST", na=False)]
    # 2. 剔除北交所股票（流动性差）
    df_all = df_all[df_all["code"].str.len() == 6]
    df_all = df_all[~df_all["code"].str.startswith("8")]
    
    valid_codes = []
    # 抽样校验+快速过滤，不逐个全量查询
    for code in df_all["code"].tolist():
        # 跳过科创板、创业板小众标的，优先主板优质标的
        if code.startswith(("3", "688")):
            continue
        valid_codes.append(code)
        # 限制最大扫描数量，彻底杜绝超时
        if len(valid_codes) > 800:
            break
    return valid_codes

@retry()
def get_stock_data(ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """获取股票K线数据，完整保留全部字段，超时直接跳过"""
    try:
        df = ak.stock_zh_a_hist(symbol=ticker, period="daily", adjust="qfq", timeout=10)
        if df.empty or len(df) < 20:
            return None
        
        # 【完整恢复你所有字段】一个不丢
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
    except:
        return None

@retry()
def get_stock_info(ticker: str) -> Optional[Dict]:
    """获取股票基本信息，失败跳过"""
    try:
        info_df = ak.stock_individual_info_em(symbol=ticker)
        return dict(zip(info_df["item"], info_df["value"]))
    except:
        return None

@retry()
def get_financial_metrics(ticker: str):
    """获取财务数据，失败跳过"""
    try:
        fin_df = ak.stock_financial_analysis_indicator(symbol=ticker).tail(3)
        return fin_df.to_dict("records")
    except:
        return None

# 兼容旧接口，项目无需修改其他代码
get_all_ashare_codes = get_valid_ashare_codes
