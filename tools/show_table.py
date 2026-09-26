#!/usr/bin/env python3
"""
show_table.py — 把构建产物里的某张表格单独抠出来渲染截图，方便核对排版。

用法：python show_table.py dist/wiki/channel/index.html 正式名/性转 out.png
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
page, needle, out = sys.argv[1], sys.argv[2], sys.argv[3]
# dist 相对脚本位置解析，免得受当前工作目录影响
dist = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist"))

html = open(page, encoding="utf-8").read()
idx = html.find(needle)
if idx < 0:
    raise SystemExit(f"页面里找不到 {needle!r}")

# 往前找最近的 <table，往后找配对的 </table>
start = html.rfind("<table", 0, idx)
depth, i = 0, start
end = -1
for m in re.finditer(r"</?table\b", html[start:]):
    if m.group(0).startswith("</"):
        depth -= 1
        if depth == 0:
            end = start + m.end() + len(">")
            break
    else:
        depth += 1
table = html[start:end]
print(f"抠出表格：{len(table)} 字节")

doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<link rel="stylesheet" href="/fonts/wenkai.css">
<link rel="stylesheet" href="/stylesheets/extra.css">
<style>
 body{{margin:0;padding:24px;font-family:"LXGW WenKai Screen","Microsoft YaHei",system-ui,sans-serif;
   font-size:15px;line-height:1.75;background:#fff}}
 table{{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%}}
 th,td{{border:1px solid #dcdfe8;padding:6px 10px;white-space:nowrap}}
 th{{background:#f3f3f7;position:sticky;top:0}}
 a{{color:#6d5bd0}}
</style></head><body>
{table}
</body></html>"""

tmp = os.path.join(dist, "_table.html")
open(tmp, "w", encoding="utf-8").write(doc)

srv = subprocess.Popen([sys.executable, "-m", "http.server", "8132", "--bind", "127.0.0.1"],
                       cwd=dist, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    import time, urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen("http://127.0.0.1:8132/", timeout=2)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    if os.path.exists(out):
        os.remove(out)
    profile = os.path.join(os.environ["TEMP"], "edge-table")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                    f"--user-data-dir={profile}", "--window-size=1260,760",
                    f"--screenshot={out}", "http://127.0.0.1:8132/_table.html"],
                   capture_output=True, timeout=120)
    print("截图:", out, os.path.exists(out))
finally:
    srv.terminate()
    time.sleep(0.3)
    try:
        os.remove(tmp)
    except OSError:
        pass
