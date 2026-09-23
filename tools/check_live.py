#!/usr/bin/env python3
"""验证 GitHub Pages 上线的站点是否真的可用。"""
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
    ("首页", "/", "王维诗里的MBTI", "text/html"),
    ("维基首页", "/wiki/", "角色档案", "text/html"),
    ("频道页", "/wiki/channel/", "视频列表", "text/html"),
    ("角色页", "/wiki/characters/haose-istj/", "郝瑟", "text/html"),
    ("理论页", "/wiki/theory/jung-eight-functions/", "荣格", "text/html"),
    ("标签页", "/tags/", "蓝人组", "text/html"),
    ("博客页", "/blog/", "博客", "text/html"),
    ("搜索索引", "/search/search_index.json", "郝瑟", "application/json"),
    ("站点地图", "/sitemap.xml", "dannyparticle.github.io", "xml"),
    ("角色立绘", "/assets/wiki-images/QQ20250728-023541.webp", None, "image/webp"),
    ("样式表", "/stylesheets/extra.css", "wiki-infobox", "text/css"),
]

ok = fail = 0
for label, path, needle, want_type in CHECKS:
    url = BASE + urllib.parse.quote(path)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verify)"})
    result = None
    last_err = ""
    # 国内到 GitHub Pages 的连接常常中途断掉，重试几次再判定
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context()) as r:
                body = r.read()
                ctype = r.headers.get("Content-Type", "")
                text_ok = True
                if needle:
                    text_ok = needle in body.decode("utf-8", "replace")
                type_ok = (want_type in ctype) if want_type else True
                flag = "✓" if (text_ok and type_ok) else "✗"
                if flag == "✓":
                    ok += 1
                else:
                    fail += 1
                extra = "" if text_ok else f"（未找到“{needle}”）"
                note = f"（第 {attempt + 1} 次尝试成功）" if attempt else ""
                print(f"  {flag} {label:<8} HTTP {r.status}  {len(body)/1024:>8.1f} KB  "
                      f"{ctype.split(';')[0]:<24}{extra}{note}")
                result = "done"
                break
        except urllib.error.HTTPError as e:
            print(f"  ✗ {label:<8} HTTP {e.code} {e.reason}")
            fail += 1
            result = "done"
            break
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:60]}"
            time.sleep(2)
    if result is None:
        fail += 1
        print(f"  ✗ {label:<8} 重试 4 次仍失败 —— {last_err}")

print(f"\n通过 {ok} 项，失败 {fail} 项")
print(f"站点地址：{BASE}/")
