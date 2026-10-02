#!/usr/bin/env python3
"""
show_section.py —— 把构建产物里某一节内容单独抠出来渲染截图。

页面上的折叠块默认是收起的，直接整页截图看不到里面的内容。
这个工具抽出一节、把所有 <details> 展开，再套上页面自身的样式表截图。

用法：python show_section.py dist/wiki/channel/index.html 视频列表 out.png
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
_HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.abspath(os.path.join(_HERE, "..", "dist"))
PORT = 8136

page, heading, out = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
html = open(page, encoding="utf-8").read()

m = re.search(rf'<h2 id="{re.escape(heading)}"', html)
if not m:
    raise SystemExit(f"找不到标题 {heading!r}")
start = m.start()
nxt = re.search(r"<h2 id=", html[m.end():])
end = m.end() + nxt.start() if nxt else len(html)
section = html[start:end]
# 默认展开所有折叠块（否则截出来是空的）；加 --keep-closed 看收起状态
if "--keep-closed" not in sys.argv:
    section = section.replace("<details>", "<details open>")
print(f"抽出「{heading}」：{len(section)} 字节，折叠块 {section.count('<details')} 个")

links = list(dict.fromkeys(re.findall(r'<link[^>]+href="[^"]*\.css"[^>]*>', html)))
html_attrs = re.sub(r'\s*class="[^"]*"', "", (re.search(r"<html([^>]*)>", html) or [None, ""])[1])
body_attrs = (re.search(r"<body([^>]*)>", html) or [None, ""])[1]

doc = f"""<!doctype html><html{html_attrs}><head><meta charset="utf-8">
{chr(10).join(links)}
<style>body{{margin:0;padding:20px}}.sl-markdown-content{{padding:0}}</style>
</head><body{body_attrs}>
<div class="sl-markdown-content">{section}</div>
</body></html>"""

tmp = os.path.join(DIST, "_section.html")
open(tmp, "w", encoding="utf-8").write(doc)

srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                       cwd=DIST, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    import urllib.request
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    if os.path.exists(out):
        os.remove(out)
    profile = os.path.join(os.environ["TEMP"], "edge-section")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                    f"--user-data-dir={profile}", "--window-size=1300,1150",
                    f"--screenshot={out}", f"http://127.0.0.1:{PORT}/_section.html"],
                   capture_output=True, timeout=150)
    print("截图:", out, os.path.exists(out))
finally:
    srv.terminate()
    time.sleep(0.3)
    try:
        os.remove(tmp)
    except OSError:
        pass
