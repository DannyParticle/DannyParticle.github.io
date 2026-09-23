#!/usr/bin/env python3
"""校验 infer_tags()：用源文件里已有的分类，检查推断结果是否与之一致。

判定标准：
  * 矛盾  —— 推断出的四色分组与源文件不同（这是真错误，必须为 0）
  * 补全  —— 分组一致，但源文件少写了部分字母标签，推断把它补齐了
  * 不适用 —— 标题里没有人格类型（例如「王元元」），推断不出东西，源分类原样保留
"""
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mw2md import infer_tags  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NS = "{http://www.mediawiki.org/xml/export-0.11/}"
GROUPS = {"紫人组", "绿人组", "蓝人组", "黄人组"}
LETTER = re.compile(r"[IENSTFJP]人")

root = ET.parse(sys.argv[1]).getroot()
conflicts = completed = na = agree = 0

for p in root.findall(NS + "page"):
    if p.findtext(NS + "ns") != "0":
        continue
    title = p.findtext(NS + "title") or ""
    rev = p.find(NS + "revision")
    text = ""
    if rev is not None:
        t = rev.find(NS + "text")
        if t is not None and t.text:
            text = t.text
    source = {c.strip() for c in re.findall(r"\[\[\s*Category\s*:\s*([^\]|]+)", text, re.I)}
    src_groups = source & GROUPS
    src_letters = {c for c in source if LETTER.fullmatch(c)}
    if not src_groups:
        continue

    mine = set(infer_tags(title))
    my_groups, my_letters = mine & GROUPS, {c for c in mine if LETTER.fullmatch(c)}

    if not mine:
        na += 1
        verdict = "不适用"
    elif my_groups != src_groups:
        conflicts += 1
        verdict = "矛盾"
    elif my_letters > src_letters:
        completed += 1
        verdict = "补全"
    else:
        agree += 1
        verdict = "一致"

    extra = f"（源只写了 {'、'.join(sorted(src_letters)) or '无'}，推断补齐 {'、'.join(sorted(my_letters - src_letters))}）" \
        if verdict == "补全" else ""
    print(f"  [{verdict}] {title:<22} 分组={sorted(src_groups) or sorted(my_groups)}{extra}")

print(f"\n有分类的正文页共 {agree + completed + conflicts + na} 个：")
print(f"  一致 {agree}　补全 {completed}　不适用 {na}　矛盾 {conflicts}")
print("  ✓ 推断与源数据没有冲突" if conflicts == 0 else f"  ✗ 存在 {conflicts} 处矛盾，需要修正")
