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


# 指向同仓库其它 .md 的相对链接（排除外链、站内绝对路径、纯锚点）
MD_LINK = re.compile(r"\]\((?!https?:|/|#|mailto:)([^)#]+?)\.md(#[^)]*)?\)")


def rewrite_md_links(text: str, rel_path: str) -> tuple[str, int]:
    """把相对 .md 链接改写成站点绝对 URL。

    Starlight 的 docsLoader 不会替你解析相对 Markdown 链接 —— 实测
    `characters/huzi-intj.md` 会原样输出到 HTML 里，从 /wiki/channel/ 打开就是 404。
    这里按「相对当前文件」解析出目标文件，再换算成它的 URL。
    """
    base = os.path.dirname(rel_path)          # 相对 wiki/ 的目录
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        target, anchor = m.group(1).strip(), m.group(2) or ""
        joined = os.path.normpath(os.path.join(base, target)).replace("\\", "/")
        if joined == "index":
            joined = ""
        elif joined.endswith("/index"):
            joined = joined[: -len("/index")]
        url = "/wiki/" + joined
        if not url.endswith("/"):
            url += "/"
        count += 1
        return f"]({url}{anchor})"

    return MD_LINK.sub(repl, text), count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="MkDocs 的 docs/wiki 目录")
    ap.add_argument("--docs", required=True, help="Astro 的 src/content/docs/wiki 目录")
    ap.add_argument("--public", required=True, help="Astro 的 public 目录")
    ap.add_argument("--images", required=True, help="图片源目录")
    ap.add_argument("--force", action="store_true",
                    help="覆盖目标目录里内容不同的文件（默认跳过，保护编辑器里改过的内容）")
    args = ap.parse_args()

    # 注意：不能先清空目标目录 —— 站点上线后 /admin/ 编辑器会直接改这里，
    # 目录里既有「编辑器改过的版本」，也可能有「编辑器新建的页面」。
    # 下面逐个文件比对，只写内容一致的（即没有被编辑器动过的）。
    os.makedirs(args.docs, exist_ok=True)
    force = args.force
    kept: list[str] = []

    written = 0
    links = 0
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
            text, n_links = rewrite_md_links(text, rel)
            links += n_links

            dest = os.path.join(args.docs, rel)
            if os.path.exists(dest) and not force:
                current = open(dest, encoding="utf-8").read()
                if current != text:
                    kept.append(rel)
                    continue
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
        d = os.path.join(dst_img, fn)
        if not os.path.isfile(s):
            continue
        # 源目录和目标目录常常是同一个，跳过自身拷贝
        if os.path.exists(d) and os.path.samefile(s, d):
            continue
        shutil.copy2(s, d)
        copied += 1

    print(f"页面 {written} 个 → {args.docs}")
    print(f"内部链接 {links} 条已改写为站点绝对路径")
    print(f"图片 {copied} 张 → {dst_img}")
    if kept:
        print(f"\n⚠ 有 {len(kept)} 个页面内容与源文件不一致，已跳过（多半是编辑器里改过的）：")
        for rel in kept[:10]:
            print(f"    {rel}")
        if len(kept) > 10:
            print(f"    … 还有 {len(kept) - 10} 个")
        print("  要强制覆盖请加 --force")

    # 自检：不该再剩下 .md 链接
    leftover = []
    for dirpath, _dirs, files in os.walk(args.docs):
        for fn in files:
            if fn.endswith(".md"):
                p = os.path.join(dirpath, fn)
                t = open(p, encoding="utf-8").read()
                if re.search(r"\]\((?!https?:|/|#)[^)]*\.md", t):
                    leftover.append(os.path.relpath(p, args.docs))
    if leftover:
        print(f"  ⚠ 仍有 .md 链接未改写：{leftover[:5]}")
    else:
        print("  ✓ 没有残留的相对 .md 链接")
    return 0


if __name__ == "__main__":
    sys.exit(main())
