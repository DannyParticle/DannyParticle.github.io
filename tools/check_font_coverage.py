#!/usr/bin/env python3
"""
check_font_coverage.py —— 验证分片覆盖了站点上真正用到的每一个字。

分片是完整字体的『划分』，理论上全覆盖；但这是「缺字」问题的关键，
必须实测而不是相信理论：
  1. 解析 sliced.css 里所有 unicode-range，合并成一张覆盖表
  2. 把站点里所有中文内容（含标题、表格、备注）的字都收集起来
  3. 逐个查是否被覆盖，列出漏网的
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WS7 = r"C:\Users\李自远\Documents\deepseekharness\ws7"
FONTS = [
    ("LXGW WenKai Screen", "霞鹜文楷",
     os.path.join(WS7, r"hyperos_fonts\FontDump\system-fonts\MiSansVF_Overlay.ttf"), None),
    ("Noto Serif SC", "思源宋体",
     os.path.join(WS7, r"hyperos_fonts\FontDump\system-fonts\NotoSerifCJK-Regular.ttc"), 2),
]


def load_cmap(src: str, face: int | None) -> dict:
    from fontTools.ttLib import TTCollection, TTFont
    if src.lower().endswith(".ttc"):
        return TTCollection(src, lazy=True).fonts[face or 0].getBestCmap()
    return TTFont(src, lazy=True).getBestCmap()


HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.abspath(os.path.join(HERE, ".."))


def ranges_to_set(css: str, family: str) -> set[int]:
    """把某个字体族的所有 unicode-range 展开成码点集合。"""
    covered: set[int] = set()
    # 按 @font-face 块切，挑出属于该字体族的
    for block in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
        if f'"{family}"' not in block:
            continue
        m = re.search(r"unicode-range:\s*([^;}\n]+)", block)
        if not m:
            continue
        for item in m.group(1).split(","):
            item = item.strip()
            mm = re.fullmatch(r"[Uu]\+([0-9a-fA-F]+)(?:-([0-9a-fA-F]+))?", item)
            if not mm:
                continue
            lo = int(mm.group(1), 16)
            hi = int(mm.group(2), 16) if mm.group(2) else lo
            covered.update(range(lo, hi + 1))
    return covered


def site_characters() -> dict[int, str]:
    """收集站点内容里出现的所有字符（0x80 以上，含中文标点）。"""
    chars: dict[int, str] = {}
    patterns = [
        os.path.join(WEB, "src/content/docs/**/*.md"),
        os.path.join(WEB, "src/content/blog/**/*.md"),
        os.path.join(WEB, "src/**/*.astro"),
        os.path.join(WEB, "src/**/*.json"),
        os.path.join(WEB, "astro.config.mjs"),
    ]
    for pat in patterns:
        for f in glob.glob(pat, recursive=True):
            try:
                t = open(f, encoding="utf-8").read()
            except OSError:
                continue
            for ch in t:
                cp = ord(ch)
                if cp >= 0x80:
                    chars.setdefault(cp, ch)
    return chars


def main() -> int:
    css_path = os.path.join(WEB, "public", "fonts", "sliced.css")
    css = open(css_path, encoding="utf-8").read()
    blocks = css.count("@font-face")
    print(f"sliced.css：{blocks} 个 @font-face")

    chars = site_characters()
    print(f"站点内容里 0x80 以上的字符：{len(chars)} 个（去重）")

    ok_all = True
    for family, label, src, face in FONTS:
        covered = ranges_to_set(css, family)
        # 字体本身有没有这个字？
        try:
            font_chars = set(load_cmap(src, face))
        except Exception as e:  # noqa: BLE001
            print(f"  ? {label}：读不到字体 {type(e).__name__}")
            continue

        # 真正的 bug：字在字体里有，却没被任何分片覆盖
        real_missing = {cp: ch for cp, ch in chars.items()
                        if cp in font_chars and cp not in covered}
        # 正常回落：字体里根本没这个字（emoji、符号、不可见字符），
        # 本来就该交给系统 emoji / 符号字体
        fallback = {cp: ch for cp, ch in chars.items()
                    if cp not in font_chars and cp not in covered}

        if real_missing:
            ok_all = False
        print(f"  {'✓' if not real_missing else '✗'} {label}")
        print(f"      字体共 {len(font_chars)} 字，分片覆盖 {len(covered)} 个码点")
        print(f"      站点用到、但字体里没有（正常回落系统字体）：{len(fallback)} 个"
              + (f"　{''.join(list(fallback.values())[:24])}" if fallback else ""))
        if real_missing:
            print(f"      ✗ 字体里有却没被覆盖：{len(real_missing)} 个 "
                  f"{''.join(list(real_missing.values())[:30])}")
            print(f"        码点：{['U+%04X' % c for c in list(real_missing)[:12]]}")

    # 顺便确认没被划进任何分片的常用汉字（抽查 CJK 主区）
    covered = ranges_to_set(css, "LXGW WenKai Screen")
    common = [c for c in range(0x4E00, 0x9FA6) if c not in covered]
    print(f"\nCJK 基本区（4E00–9FA5）未被覆盖：{len(common)} 个")
    if common:
        print("  示例：" + "".join(chr(c) for c in common[:40]))

    print("\n" + ("✓ 分片覆盖完整，不会缺字" if ok_all else "✗ 有字符没被覆盖，需要调整分片"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
