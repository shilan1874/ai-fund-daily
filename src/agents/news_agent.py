import akshare as ak


def get_daily_finance_news() -> str:
    """Get the latest China A-share market finance news headlines."""
    try:
        df = ak.stock_info_global_cls(symbol="全部")
        title_col = "标题" if "标题" in df.columns else "title"
        news_list = df[title_col].dropna().head(8).tolist()
        return "\n".join([f"- {title}" for title in news_list])
    except Exception as exc:
        return f"今日新闻获取异常：{exc}"


def get_market_overview() -> str:
    """Get Shanghai index, northbound funds, and hot industry sectors."""
    close_text = "暂未获取"
    north_net_text = "暂未获取"
    hot_sectors_text = "暂未获取"

    try:
        index_df = ak.stock_zh_index_daily(symbol="sh000001")
        close_text = f"{float(index_df.iloc[-1]['close']):.2f}"
    except Exception:
        pass

    try:
        north_df = ak.stock_hsgt_fund_flow_summary_em()
        amount_col = "今日资金净流入" if "今日资金净流入" in north_df.columns else "净流入"
        if amount_col in north_df.columns:
            north_net_text = str(north_df[amount_col].iloc[0])
    except Exception:
        pass

    try:
        sector_df = ak.stock_board_industry_name_em()
        hot_df = sector_df.sort_values("涨跌幅", ascending=False).head(5)
        hot_sectors_text = ", ".join(hot_df["板块名称"].tolist())
    except Exception:
        pass

    return f"上证指数：{close_text}\n北向资金净流入：{north_net_text}\n热门板块：{hot_sectors_text}"
