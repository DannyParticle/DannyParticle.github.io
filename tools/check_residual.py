#!/usr/bin/env python3
"""扫描转换后的 Markdown，报告残留的 wikitext 痕迹与结构问题。"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATTERNS = {
    "{{模板}}": r"\{\{",
    "[[内部链接]]": r"\[\[",
    "}}": r"\}\}",
    "]]": r"\]\]",
    "'''三撇粗体'''": r"'''",
    "{|表格": r"\{\|",
    "|}": r"\|\}",
    "<nowiki>": r"<nowiki",
    "<ref>": r"<ref",
    "图片未找到": r"未找到",
    "#REDIRECT": r"#REDIRECT",
    "-{语言变体}-": r"-\{",
    "<gallery>": r"<gallery",
    "空标签<>": r"<[a-z/][^>]*>\s*<[a-z/]",
}

root = sys.argv[1] if len(sys.argv) > 1 else "wiki-migration/site/docs/wiki"
files = sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True))

totals: dict[str, int] = {k: 0 for k in PATTERNS}
where: dict[str, list[tuple[str, int]]] = {}

for f in files:
    text = open(f, encoding="utf-8").read()
    rel = os.path.relpath(f, root)
    for key, pat in PATTERNS.items():
        n = len(re.findall(pat, text))
        if n:
            totals[key] += n
            where.setdefault(key, []).append((rel, n))

print(f"扫描 {len(files)} 个文件：{root}\n")
bad = False
for key, n in totals.items():
    if n:
        bad = True
        sample = ", ".join(f"{f}×{c}" for f, c in where[key][:4])
        print(f"  ⚠ {key}: {n} 处  → {sample}")
if not bad:
    print("  ✓ 没有残留的 wikitext 标记")

# 结构检查
print("\n结构检查：")
issues = 0
for f in files:
    rel = os.path.relpath(f, root)
    text = open(f, encoding="utf-8").read()
    lines = text.split("\n")
    if not text.startswith("---\n"):
        print(f"  ⚠ {rel}: 缺少 front matter"); issues += 1
    # Astro/Starlight 用 frontmatter 的 title 渲染大标题，正文里不该再有 H1；
    # 出现多个 H1 才是问题（标题会重复显示）。
    h1 = [ln for ln in lines if ln.startswith("# ")]
    if len(h1) > 1:
        print(f"  ⚠ {rel}: 一级标题有 {len(h1)} 个（应 ≤ 1，多出来的会重复显示）"); issues += 1
if not issues:
    print("  ✓ front matter 与标题结构正常")

# Markdown 表格结构检查
# 表格一旦被换行撑断（单元格里带 \n），整张表会退化成一段普通文字，
# 页面上就是一堆竖线 —— 这里把这种表找出来。
print("\nMarkdown 表格检查：")
table_bad = 0
table_ok = 0
for f in files:
    rel = os.path.relpath(f, root)
    lines = open(f, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines):
        if not lines[i].startswith("|"):
            i += 1
            continue
        block = []
        while i < len(lines) and lines[i].strip():
            block.append(lines[i]); i += 1
        # 表格块里的每一行都应以 | 开头；出现「表头 + 分隔行」才算合法
        broken_lines = [b for b in block if not b.startswith("|")]
        has_sep = len(block) > 1 and re.fullmatch(r"\|[\s\-:|]+\|", block[1] or "")
        if broken_lines or not has_sep:
            table_bad += 1
            head = (block[0][:60] + "…") if block else ""
            why = "块内有非表格行" if broken_lines else "缺少分隔行 |---|"
            print(f"  ⚠ {rel}: {why} —— {head}")
        else:
            table_ok += 1
if table_bad == 0:
    print(f"  ✓ {table_ok} 张表格结构正常")

# 内部链接检查
print("\n内部链接检查：")
broken = 0
for f in files:
    rel = os.path.relpath(f, root)
    text = open(f, encoding="utf-8").read()
    for m in re.finditer(r"\]\(([^)#:]+\.md)\)", text):
        target = m.group(1)
        dest = os.path.normpath(os.path.join(os.path.dirname(f), target))
        if not os.path.exists(dest):
            print(f"  ⚠ {rel} → {target} 不存在"); broken += 1
if not broken:
    print("  ✓ 所有 .md 内部链接都有效")

# 图片检查
print("\n图片引用检查：")
refs = {}
for f in files:
    text = open(f, encoding="utf-8").read()
    for m in re.finditer(r'src="([^"]+)"|!\[[^\]]*\]\(([^)]+)\)', text):
        src = m.group(1) or m.group(2)
        if src.startswith("http"):
            continue
        refs[src] = refs.get(src, 0) + 1

# 绝对路径（/wiki-images/x.webp）由 Astro 从 public/ 提供，
# 相对路径则相对 Markdown 文件本身解析。
public_dir = None
probe = os.path.abspath(root)
for _ in range(6):
    cand = os.path.join(probe, "public")
    if os.path.isdir(cand):
        public_dir = cand
        break
    probe = os.path.dirname(probe)

missing = []
for s in refs:
    if s.startswith("/"):
        hit = public_dir and os.path.exists(os.path.join(public_dir, s.lstrip("/")))
    else:
        hit = os.path.exists(os.path.join(root, s))
    if not hit:
        missing.append(s)
print(f"  引用图片 {len(refs)} 个（去重），缺失 {len(missing)} 个"
      + (f"（静态资源目录：{os.path.relpath(public_dir, os.path.dirname(root))}）" if public_dir else ""))
for s in missing[:6]:
    print(f"    - {s}")
