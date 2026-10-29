#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地工具箱 · 仓库流量统计采集脚本
每天抓取 GitHub 仓库的 clone / view / release download 数据，累计写入 stats/stats.json。

依赖：仅 Python 标准库（urllib），无需安装任何包。
运行：由 .github/workflows/stats.yml 定时调用，也可本地手动运行（需 GITHUB_TOKEN）。
"""
import os, json, sys, datetime, urllib.request, urllib.error

REPO = os.environ.get("REPO", "")              # 形如 owner/repo
TOKEN = os.environ.get("GITHUB_TOKEN", "")
STATS_FILE = "stats/stats.json"
UA = "local-toolbox-stats-bot"

def api(path):
    url = f"https://api.github.com/repos/{REPO}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  [warn] GET {path} -> HTTP {e.code}")
        return None

def default_stats():
    return {
        "last_updated": None,
        "total_clones": 0,
        "total_views": 0,
        "total_downloads": 0,
        "uniques_14d": {"clones": 0, "views": 0},
        "seen_dates": [],          # 已累计过的日期，用于避免重复累计
        "recent": [],              # 最近 14 天每日记录
    }

def main():
    if not REPO or not TOKEN:
        print("错误：需要设置 REPO 和 GITHUB_TOKEN 环境变量")
        sys.exit(1)

    # 读取旧的累计数据
    stats = default_stats()
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        stats.setdefault("seen_dates", [])
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)

    # 1) Clone 数据（仅最近 14 天）
    clones = api("/traffic/clones")
    if clones and clones.get("count") is not None:
        stats["uniques_14d"]["clones"] = clones.get("uniques", 0)
        for item in clones.get("clones", []):
            d = item.get("timestamp", "")[:10]
            if d and d not in stats["seen_dates"]:
                stats["total_clones"] += item.get("count", 0)
                stats["seen_dates"].append(d)
                stats["recent"].append({"date": d, "kind": "clone", "count": item.get("count", 0)})

    # 2) View 数据（仅最近 14 天）
    views = api("/traffic/views")
    if views and views.get("count") is not None:
        stats["uniques_14d"]["views"] = views.get("uniques", 0)
        for item in views.get("views", []):
            d = item.get("timestamp", "")[:10]
            if d and d not in stats["seen_dates"]:
                stats["total_views"] += item.get("count", 0)
                stats["seen_dates"].append(d)
                stats["recent"].append({"date": d, "kind": "view", "count": item.get("count", 0)})

    # 3) Release 下载量（download_count 是 GitHub 自带的累计值，直接覆盖）
    releases = api("/releases")
    if isinstance(releases, list):
        total = 0
        for rel in releases:
            for asset in rel.get("assets", []):
                total += asset.get("download_count", 0)
        stats["total_downloads"] = total

    stats["last_updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # 控制 recent 长度，只留最近 60 条
    stats["recent"] = stats["recent"][-60:]

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("流量统计已更新：")
    print(f"  累计 Clone : {stats['total_clones']}")
    print(f"  累计 View  : {stats['total_views']}")
    print(f"  累计下载   : {stats['total_downloads']}")
    print(f"  写入 {STATS_FILE}")

if __name__ == "__main__":
    main()
