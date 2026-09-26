#!/usr/bin/env python3
"""验证 Astro 版线上站点：页面、字体、图片、搜索索引。"""
from __future__ import annotations

import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "https://dannyparticle.github.io"

CHECKS = [
    ("首页", "/", "王维诗里的MBTI"),
    ("资料站角色页", "/wiki/characters/haose-istj/", "郝瑟"),
    ("资料站频道页", "/wiki/channel/", "视频列表"),
    ("理论页", "/wiki/theory/jung-eight-functions/", "荣格"),
    ("博客列表", "/blog/", "全部文章"),
    ("博客文章", "/blog/fandom-to-github/", "use_directory_urls"),
    ("配对表", "/wiki/pairings/", "可左右滑动"),
    ("字体 CSS", "/fonts/wenkai.css", "LXGW WenKai Screen"),
    ("字体分片", "/fonts/files/lxgwwenkaiscreen-subset-4.woff2", None),
    ("维基图片", "/wiki-images/QQ20250728-023541.webp", None),
    ("搜索索引", "/pagefind/pagefind.js", None),
    ("站点地图", "/sitemap-index.xml", "dannyparticle"),
]


def fetch(url: str, tries: int = 5):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verify)"})
    last = ""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=45, context=ssl.create_default_context()) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, b"", ""
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}"
            time.sleep(3)
    return None, last.encode(), ""


ok = fail = 0
for label, path, needle in CHECKS:
    url = BASE + urllib.parse.quote(path)
    status, body, ctype = fetch(url)
    if status == 200 and len(body) > 20:
        hit = needle is None or needle in body.decode("utf-8", "replace")
        if hit:
            ok += 1
            print(f"  ✓ {label:<14} {len(body)/1024:>8.1f} KB  {ctype.split(';')[0]}")
        else:
            fail += 1
            print(f"  ✗ {label:<14} 200 但没找到「{needle}」")
    else:
        fail += 1
        print(f"  ✗ {label:<14} {status} {body[:50]!r}")

print(f"\n通过 {ok}/{len(CHECKS)}")
