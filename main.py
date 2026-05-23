import base64
import hashlib
import hmac
import os
import time
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

from src.agents.hedge_fund_agent import run_hedge_fund
from src.agents.news_agent import get_daily_finance_news, get_market_overview


load_dotenv()


def send_dingtalk(title: str, content: str) -> None:
    webhook = os.getenv("DINGTALK_WEBHOOK") or os.getenv("DINGDING_WEBHOOK")
    if not webhook or webhook == "your-dingtalk-webhook":
        print("未配置 DINGTALK_WEBHOOK/DINGDING_WEBHOOK，跳过钉钉推送。")
        return

    secret = os.getenv("DINGTALK_SECRET") or os.getenv("DINGDING_SECRET")
    if secret and secret != "your-dingtalk-secret":
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = quote_plus(base64.b64encode(hmac_code))
        separator = "&" if "?" in webhook else "?"
        webhook = f"{webhook}{separator}timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "text",
        "text": {
            "content": f"{title}\n\n{content}",
        },
    }
    response = requests.post(webhook, json=payload, timeout=20)
    response.raise_for_status()
    result = response.json()
    if result.get("errcode") != 0:
        raise RuntimeError(f"钉钉推送失败：{result}")


def main() -> None:
    news = get_daily_finance_news()
    market = get_market_overview()
    hedge_result = run_hedge_fund()

    report = f"""
【每日财经热点新闻】
{news}

【大盘·北向资金·热门板块】
{market}

【AI对冲基金A股精选报告】
{hedge_result}

风险提示：本内容仅为AI数据分析参考，不构成任何投资建议，股市有风险，投资需谨慎。
""".strip()

    send_dingtalk("A股每日财经+AI选股日报", report)
    print(report)


if __name__ == "__main__":
    main()
