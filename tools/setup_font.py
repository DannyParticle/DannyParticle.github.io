#!/usr/bin/env python3
"""
setup_font.py — 把霞鹜文楷（屏幕阅读版）自托管到 Astro 站点。

为什么自托管而不是挂 jsDelivr：大陆访问 jsDelivr 不稳定，
字体是首屏资源，挂了就是一大片空白。

只复制 lxgwwenkaiscreen（全量、含繁体）那一套，97 个 woff2 分片，
配合 unicode-range，浏览器只会下载页面上真正用到的那几片。
"""
from __future__ import annotations

import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC_PKG = "wiki-migration/astro-site/node_modules/lxgw-wenkai-screen-webfont"
DST = "wiki-migration/astro-site/public/fonts"
VARIANT = "lxgwwenkaiscreen"          # 全量（含繁体），另有 gb 版小 0.5MB
CSS_NAME = "wenkai.css"


def main() -> int:
    src_css = os.path.join(SRC_PKG, f"{VARIANT}.css")
    if not os.path.exists(src_css):
        print(f"找不到 {src_css}，先跑 npm install")
        return 1

    os.makedirs(os.path.join(DST, "files"), exist_ok=True)

    css = open(src_css, encoding="utf-8").read()

    # 加上 font-display: swap —— 字体没下完时先用回退字体显示，不要白屏
    if "font-display" not in css:
        css = css.replace("font-style: normal;", "font-style: normal;\n  font-display: swap;")
        css = css.replace("font-style:normal;", "font-style:normal;\n  font-display:swap;")
    # 路径从 ./files/ 保持一致
    open(os.path.join(DST, CSS_NAME), "w", encoding="utf-8").write(css)

    copied = size = 0
    for fn in os.listdir(os.path.join(SRC_PKG, "files")):
        if fn.startswith(VARIANT + "-") and fn.endswith(".woff2"):
            s = os.path.join(SRC_PKG, "files", fn)
            shutil.copy2(s, os.path.join(DST, "files", fn))
            copied += 1
            size += os.path.getsize(s)

    n_face = css.count("@font-face")
    has_swap = "font-display" in css
    print(f"字体 CSS  → {os.path.join(DST, CSS_NAME)}（{n_face} 个 @font-face，font-display={'已加' if has_swap else '无'}）")
    print(f"字体分片  → {os.path.join(DST, 'files')}（{copied} 个 woff2，共 {size/1024/1024:.2f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
