#!/usr/bin/env python3
"""
check_links.py — 检查构建产物里的站内链接是否都能落地。

Starlight 不会替我们解析相对 .md 链接，所以内链一旦没改写就会全站 404。
这里把 dist 里每个 HTML 的 href 抽出来，逐个对到磁盘上的文件。
"""
from __future__ import annotations

import os
import re
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIST = sys.argv[1] if len(sys.argv) > 1 else "wiki-migration/web/dist"
HREF = re.compile(r'href="([^"]+)"')

pages = []
for dirpath, _dirs, files in os.walk(DIST):
    for fn in files:
        if fn.endswith(".html") and not fn.startswith("_"):
            pages.append(os.path.join(dirpath, fn))

broken: dict[str, list[str]] = {}
checked = 0
for page in pages:
    html = open(page, encoding="utf-8").read()
    rel_page = os.path.relpath(page, DIST).replace("\\", "/")
    for href in HREF.findall(html):
        if href.startswith(("http://", "https://", "mailto:", "#", "//")):
            continue
        path = urllib.parse.urlparse(href).path
        if not path:
            continue
        checked += 1
        # 去掉 base 前缀后映射到磁盘
        target = path.lstrip("/")
        cand = os.path.join(DIST, target)
        ok = (os.path.isfile(cand)
              or os.path.isfile(os.path.join(cand, "index.html"))
              or os.path.isdir(cand))
        if not ok:
            broken.setdefault(rel_page, []).append(href)

print(f"扫描 {len(pages)} 个页面，检查 {checked} 条站内链接")
if broken:
    total = sum(len(v) for v in broken.values())
    print(f"\n✗ 有 {total} 条链接落不到文件上：")
    for page, hrefs in list(broken.items())[:12]:
        for h in hrefs[:5]:
            print(f"  {page}  →  {h}")
    sys.exit(1)
print("✓ 所有站内链接都能落地")
