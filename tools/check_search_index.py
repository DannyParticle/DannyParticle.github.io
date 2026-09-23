#!/usr/bin/env python3
"""确认线上搜索索引里真的包含中文内容（JSON 会把中文转义成 \\uXXXX）。"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

url = "https://dannyparticle.github.io/search/search_index.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verify)"})
with urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context()) as r:
    data = json.loads(r.read().decode("utf-8"))

docs = data.get("docs", [])
print(f"搜索索引：{len(docs)} 条文档，config.lang = {data.get('config', {}).get('lang')}")

titles = [d.get("title", "") for d in docs]
hits = [t for t in titles if "郝瑟" in t or "荣格" in t or "王维诗里的MBTI" in t]
print(f"包含中文标题的条目：{len(hits)} 条，例如：{hits[:5]}")

# 抽查一条正文里是否有中文分词后的内容
sample = next((d for d in docs if "郝瑟" in d.get("title", "")), None)
if sample:
    text = sample.get("text", "")
    print(f"\n样例文档：{sample['title']}")
    print(f"  正文长度 {len(text)} 字，前 80 字：{text[:80]}")
    print(f"  含「机器人」：{'机器人' in text}")
else:
    print("\n! 没有找到角色页的索引条目")
