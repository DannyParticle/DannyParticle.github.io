#!/usr/bin/env python3
"""把线上 sitemap 里的每个页面都跑一遍，确认没有 404。"""
from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SITEMAP = "https://dannyparticle.github.io/sitemap.xml"


def fetch(url: str, tries: int = 4):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verify)"})
    last = ""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context()) as r:
                return r.status, r.read(), attempt
        except urllib.error.HTTPError as e:
            return e.code, b"", attempt
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:50]}"
            time.sleep(2)
    return None, last.encode(), tries


status, body, _ = fetch(SITEMAP)
if status != 200:
    raise SystemExit(f"sitemap 取不到：{status} {body[:120]!r}")

urls = re.findall(r"<loc>([^<]+)</loc>", body.decode("utf-8"))
print(f"sitemap 里有 {len(urls)} 个页面，逐个检查…\n")

ok = fail = 0
failed = []
for i, url in enumerate(urls, 1):
    st, payload, attempt = fetch(url)
    label = urllib.parse.unquote(url.replace("https://dannyparticle.github.io/", "")) or "/"
    if st == 200 and len(payload) > 500:
        ok += 1
        if i % 10 == 0 or i == len(urls):
            print(f"  已检查 {i}/{len(urls)}…")
    else:
        fail += 1
        failed.append((label, st, len(payload)))
        print(f"  ✗ {label}  HTTP {st}  {len(payload)}B")

print(f"\n结果：{ok} 个正常，{fail} 个异常")
for label, st, n in failed:
    print(f"  - {label} → HTTP {st}")
