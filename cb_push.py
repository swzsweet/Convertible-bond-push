#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每天查询当日可申购的可转债，并通过 Bark 推送。

数据来源：东方财富 可转债申购列表
推送通道：Bark (https://api.day.app/<key>/<内容>?group=&copy=)
"""

import os
import re
import sys
import time
import logging
from datetime import datetime, date
from urllib.parse import quote

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("cb_push")

# 东方财富可转债申购数据接口
EASTMONEY_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ---- 配置（环境变量）----
# BARK_BASE 形如 https://api.day.app/your_key  （末尾不带斜杠也可）
# 支持多个地址，用逗号或分号分隔，会逐个推送
def _parse_bases(raw: str):
    parts = re.split(r"[,;\s]+", raw.strip())
    return [p.rstrip("/") for p in parts if p.strip()]


BARK_BASES = _parse_bases(os.environ.get("BARK_BASE", ""))
BARK_GROUP = os.environ.get("BARK_GROUP", "可转债")
# 推送时间，HH:MM，默认 09:00
PUSH_TIME = os.environ.get("PUSH_TIME", "09:00")
# 没有可申购可转债时是否也推送一条提示
NOTIFY_WHEN_EMPTY = os.environ.get("NOTIFY_WHEN_EMPTY", "false").lower() == "true"
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "20"))


def fetch_bonds(page_size: int = 50):
    """拉取最新的可转债申购列表。"""
    params = {
        "sortColumns": "PUBLIC_START_DATE",
        "sortTypes": "-1",
        "pageSize": str(page_size),
        "pageNumber": "1",
        "reportName": "RPT_BOND_CB_LIST",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://data.eastmoney.com/",
    }
    resp = requests.get(
        EASTMONEY_API, params=params, headers=headers, timeout=REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("result") or {}
    return result.get("data") or []


def today_subscribable(bonds, today: date):
    """过滤出网上申购日为今天的可转债。"""
    out = []
    for b in bonds:
        raw = b.get("PUBLIC_START_DATE")
        if not raw:
            continue
        try:
            d = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d == today:
            out.append(b)
    return out


def build_message(bonds):
    """根据可申购的可转债构建推送标题与正文。"""
    lines = []
    for b in bonds:
        name = b.get("SECURITY_NAME_ABBR", "未知")
        apply_code = b.get("CORRECODE", "-")
        rating = b.get("RATING", "-")
        stock = b.get("SECURITY_SHORT_NAME", "-")
        scale = b.get("ACTUAL_ISSUE_SCALE")
        scale_str = f"{scale}亿" if scale is not None else "-"
        lines.append(
            f"{name} 申购代码:{apply_code} 评级:{rating} "
            f"正股:{stock} 规模:{scale_str}"
        )
    title = f"今日可申购可转债 {len(bonds)} 只"
    body = "\n".join(lines)
    return title, body


def _push_one(base: str, title: str, body: str, copy_text: str = ""):
    """向单个 Bark 地址推送。"""
    # Bark URL: /<key>/<title>/<body>
    url = f"{base}/{quote(title)}/{quote(body)}"
    params = {"group": BARK_GROUP}
    if copy_text:
        params["copy"] = copy_text
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        log.info("推送成功 -> %s : %s", base, title)
        return True
    except requests.RequestException as e:
        log.error("推送失败 -> %s : %s", base, e)
        return False


def push_bark(title: str, body: str, copy_text: str = ""):
    """通过 Bark 推送，支持多个地址，逐个发送。"""
    if not BARK_BASES:
        log.error("未配置 BARK_BASE，无法推送。")
        return False
    results = [_push_one(base, title, body, copy_text) for base in BARK_BASES]
    ok = sum(results)
    log.info("推送完成: %d/%d 成功", ok, len(results))
    return any(results)


def run_once():
    """执行一次查询并推送。"""
    today = date.today()
    log.info("查询 %s 可申购可转债...", today)
    try:
        bonds = fetch_bonds()
    except requests.RequestException as e:
        log.error("拉取数据失败: %s", e)
        return
    subscribable = today_subscribable(bonds, today)

    if subscribable:
        title, body = build_message(subscribable)
        # 复制内容默认放申购代码，方便快捷复制
        copy_text = " ".join(b.get("CORRECODE", "") for b in subscribable).strip()
        log.info("发现 %d 只可申购可转债", len(subscribable))
        push_bark(title, body, copy_text)
    else:
        log.info("今日无可申购可转债")
        if NOTIFY_WHEN_EMPTY:
            push_bark("今日无可申购可转债", f"{today} 暂无新债申购")


def seconds_until(push_time: str) -> float:
    """计算距离下一个 push_time 的秒数。"""
    now = datetime.now()
    hh, mm = (int(x) for x in push_time.split(":"))
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        # 已过今天的时间点，等到明天
        target = target.replace(day=now.day)
        from datetime import timedelta
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_daemon():
    """常驻进程，每天到点执行一次。"""
    log.info("守护进程启动，每天 %s 推送。", PUSH_TIME)
    while True:
        wait = seconds_until(PUSH_TIME)
        log.info("距离下次执行还有 %.0f 秒", wait)
        time.sleep(wait)
        run_once()
        # 防止同一分钟内重复触发
        time.sleep(60)


def main():
    if "--once" in sys.argv:
        run_once()
    else:
        run_daemon()


if __name__ == "__main__":
    main()
