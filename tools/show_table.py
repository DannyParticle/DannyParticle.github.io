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

# 直接用页面自己的样式表（Astro 会把 custom.css 打包成 /_astro/xxx.css），
# 否则排版跟线上不一致，截出来的图没有参考价值。
links = re.findall(r'<link[^>]+href="[^"]*\.css"[^>]*>', html)
links = list(dict.fromkeys(links))
print(f"引用样式表 {len(links)} 个")

# 连 <html>/<body> 的属性一起照搬 —— Starlight 的主题变量挂在 data-theme 上，
# 少了它整页配色都会不对（表头会变成黑底白字）
html_attrs = (re.search(r"<html([^>]*)>", html) or [None, ""])[1]
body_attrs = (re.search(r"<body([^>]*)>", html) or [None, ""])[1]
html_attrs = re.sub(r'\s*class="[^"]*"', "", html_attrs)
print(f"<html{html_attrs}>")

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

doc = f"""<!doctype html><html{html_attrs}><head><meta charset="utf-8">
{chr(10).join(links)}
<style>
 body{{margin:0;padding:24px}}
 .sl-markdown-content{{padding:0}}
</style></head><body{body_attrs}>
<div class="sl-markdown-content">
{table}
</div>
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
