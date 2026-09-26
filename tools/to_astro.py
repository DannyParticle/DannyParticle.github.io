#!/usr/bin/env python3
"""
to_astro.py — 把已经转好的 Markdown 适配成 Astro + Starlight 的结构。

做四件事：
  1. 图片路径改成站内绝对路径（Astro 从 public/ 提供静态资源）
  2. Material 的折叠块 ??? note "标题"  →  <details><summary>
  3. 复制图片到 public/wiki-images/
  4. 按 MkDocs 的导航结构生成 Starlight 侧边栏片段（打印出来，供人工粘进配置）
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# MkDocs 里的输出路径 → Starlight 里的路径（都在 docs/wiki 下，保持一致）
SECTIONS = [
    ("概览", ["index", "about", "channel"]),
    ("角色档案", [
        "characters/huzi-intj", "characters/shutiao-intp", "characters/lvqiangren-entj",
        "characters/guozhemei-entp", "characters/bailitouhei-infj", "characters/xiaofudie-infp",
        "characters/sudajian-enfj", "characters/xiugougou-enfp", "characters/haose-istj",
        "characters/mama-isfj", "characters/chizi-estj", "characters/shange-esfj",
        "characters/zuan-istp", "characters/liulian-isfp", "characters/mojing-estp",
        "characters/cuicui-esfp",
    ]),
    ("设定与作品", ["works/buqi", "studio", "pairings", "works/bilibili-fanworks"]),
    ("理论", ["theory/jung-eight-functions"]),
    ("相关人物", ["people/wangyuanyuan", "people/viki", "people/zhongluyinxi",
                  "people/yunzhongluyinxi", "people/hulishuashua", "people/guge"]),
]


def convert_collapsible(text: str) -> str:
    """Material 的 ??? note "标题" + 四空格缩进 → HTML details。"""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r'^\?\?\?\s*\w+\s*"(.*)"\s*$', lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        title = m.group(1)
        body: list[str] = []
        i += 1
        while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
            body.append(lines[i][4:] if lines[i].startswith("    ") else "")
            i += 1
        while body and not body[-1].strip():
            body.pop()
        out.append(f"<details>\n<summary>{title}</summary>\n")
        out.append("\n".join(body))
        out.append("\n</details>")
    return "\n".join(out)


def strip_duplicate_h1(text: str) -> str:
    """Starlight 会用 frontmatter 的 title 渲染页面大标题，
    正文里那行 `# 同名标题` 就成了重复，去掉它。"""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return text
    front = m.group(1)
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', front, re.M)
    if not title:
        return text
    body = text[m.end():]
    body = re.sub(r"^\s*#\s+" + re.escape(title.group(1).strip()) + r"\s*\n",
                  "", body, count=1)
    return text[:m.end()] + body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="MkDocs 的 docs/wiki 目录")
    ap.add_argument("--docs", required=True, help="Astro 的 src/content/docs/wiki 目录")
    ap.add_argument("--public", required=True, help="Astro 的 public 目录")
    ap.add_argument("--images", required=True, help="图片源目录")
    args = ap.parse_args()

    if os.path.exists(args.docs):
        shutil.rmtree(args.docs)
    os.makedirs(args.docs, exist_ok=True)

    written = 0
    for dirpath, _dirs, files in os.walk(args.src):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, args.src).replace("\\", "/")
            text = open(src, encoding="utf-8").read()

            # 图片路径 → 站内绝对路径
            text = re.sub(r"(?:\.\./)+assets/wiki-images/", "/wiki-images/", text)
            text = convert_collapsible(text)
            text = strip_duplicate_h1(text)

            dest = os.path.join(args.docs, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(text)
            written += 1

    # 图片
    dst_img = os.path.join(args.public, "wiki-images")
    os.makedirs(dst_img, exist_ok=True)
    copied = 0
    for fn in os.listdir(args.images):
        s = os.path.join(args.images, fn)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst_img, fn))
            copied += 1

    print(f"页面 {written} 个 → {args.docs}")
    print(f"图片 {copied} 张 → {dst_img}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
