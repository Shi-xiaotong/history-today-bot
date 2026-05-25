"""历史上的今天推送 — 飞书机器人"""

import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")
MAX_RETRIES = 3
REQUEST_TIMEOUT = 15


def fetch_json(url: str) -> dict:
    """带重试的 JSON 请求"""
    req = urllib.request.Request(url, headers={"User-Agent": "history-today-bot/1.0"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            logger.warning("请求失败 (尝试 %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            time.sleep(2 ** attempt)


def fetch_wikipedia_events(month: int, day: int) -> list:
    """从 Wikipedia 获取历史上的今天事件"""
    url = f"https://zh.wikipedia.org/api/rest_v1/feed/onthisday/events/{month:02d}/{day:02d}"
    data = fetch_json(url)
    events = []
    for item in data.get("events", [])[:10]:
        year = item.get("year", "")
        text = item.get("text", "")
        # 清理 HTML 标签
        import re
        text = re.sub(r"<[^>]+>", "", text)
        if year and text:
            events.append(f"**{year}年** — {text}")
    return events


def fetch_wikipedia_births(month: int, day: int) -> list:
    """从 Wikipedia 获取历史上的今天出生的人"""
    url = f"https://zh.wikipedia.org/api/rest_v1/feed/onthisday/births/{month:02d}/{day:02d}"
    data = fetch_json(url)
    births = []
    for item in data.get("births", [])[:5]:
        year = item.get("year", "")
        text = item.get("text", "")
        import re
        text = re.sub(r"<[^>]+>", "", text)
        if year and text:
            births.append(f"**{year}年** — {text}")
    return births


def build_card(events: list, births: list) -> dict:
    """构建飞书卡片"""
    now = datetime.now()
    month = now.month
    day = now.day
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekdays[now.weekday()]
    date_str = f"{month}月{day}日 {weekday}"

    elements = []

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**<i class=\"fas fa-calendar-day\"></i> 历史上的今天 · {date_str}**"},
    })
    elements.append({"tag": "hr"})

    if events:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**<i class=\"fas fa-scroll\"></i> 历史事件**"},
        })
        content = "\n".join(f"• {e}" for e in events)
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": content},
        })

    if births:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**<i class=\"fas fa-birthday-cake\"></i> 名人诞辰**"},
        })
        content = "\n".join(f"• {b}" for b in births)
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": content},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"历史上的今天 · {now.strftime('%Y-%m-%d %H:%M')}"}],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"历史上的今天 · {date_str}"},
            "template": "red",
        },
        "elements": elements,
    }


def send_feishu(payload: dict):
    """带重试的飞书推送"""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                result = json.loads(resp.read().decode())
                if result.get("code") != 0:
                    logger.error("飞书返回错误: %s", result)
                    sys.exit(1)
                logger.info("推送成功")
                return
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.error("飞书推送失败: %s", e)
                sys.exit(1)
            logger.warning("推送失败 (尝试 %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            time.sleep(2 ** attempt)


def main():
    if not WEBHOOK_URL:
        logger.error("请设置 FEISHU_WEBHOOK_URL 环境变量")
        sys.exit(1)

    now = datetime.now()
    month = now.month
    day = now.day

    logger.info("正在获取历史上的今天...")
    events = fetch_wikipedia_events(month, day)
    births = fetch_wikipedia_births(month, day)

    logger.info("获取到 %d 个事件, %d 个名人诞辰", len(events), len(births))
    card = build_card(events, births)
    send_feishu({"msg_type": "interactive", "card": card})


if __name__ == "__main__":
    main()
