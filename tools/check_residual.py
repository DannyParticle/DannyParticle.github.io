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
    h1 = [ln for ln in lines if ln.startswith("# ")]
    if len(h1) != 1:
        print(f"  ⚠ {rel}: 一级标题有 {len(h1)} 个（应为 1）"); issues += 1
    # 表格行长度一致性
    for i, ln in enumerate(lines):
        if ln.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").replace("-", "").strip()) == set():
            pass
    if re.search(r"^\|.*\|\s*$", text, re.M):
        pass
if not issues:
    print("  ✓ front matter 与标题结构正常")

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
docs_root = os.path.dirname(root.rstrip("/\\"))
missing = [s for s in refs if not os.path.exists(os.path.join(docs_root, s))]
print(f"  引用图片 {len(refs)} 个（去重），缺失 {len(missing)} 个")
for s in missing[:6]:
    print(f"    - {s}")
