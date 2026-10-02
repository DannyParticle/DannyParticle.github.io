#!/usr/bin/env python3
"""
slice_fonts.py —— 把允许修改的字体切成 unicode-range 分片，恢复首屏速度。

**只处理 SIL OFL 许可的字体**。MiSans 和 HarmonyOS Sans 的许可明文写着
「不得修改字体」，而分片本质就是裁掉用不到的字形 —— 属于修改，所以那两套
保持整包发布，只在被选中时才下载。

关键：分片是**完整字符集的划分**，不是取子集。做法是

  1. 读出字体自己的 cmap —— 它到底有哪些字
  2. 把**站点内容里真正出现的字**按使用频次排在前几片
     （这样正常浏览只会下到第 0～2 片）
  3. 其余所有字按码点均匀切成若干片

每一步都覆盖字体的全部字符、互不重叠。不这么做的话，像「淽」「杦」
这种既不在常用字表里、又真的写在页面上的字就会掉到系统字体 —— 看起来像缺字。

（踩过的坑：早先直接套用了 LXGW npm 包里的 unicode-range 表，但那套表只覆盖
14,492 个码点，是为那个包的子集字体设计的。套到 28,872 字的完整字体上，
就有 8660 个常用汉字没被划进任何分片。）
"""
from __future__ import annotations

import glob
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fontTools import subset                      # noqa: E402
from fontTools.subset import parse_unicodes       # noqa: E402
from fontTools.ttLib import TTCollection, TTFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(WEB, "public", "fonts")
WS7 = r"C:\Users\李自远\Documents\deepseekharness\ws7"

SITE_CHUNK = 400      # 站点用到的字，每片多少个（按频次从高到低）
REST_CHUNK = 300      # 其余字符，每片多少个（按码点顺序）

JOBS = [
    {
        "name": "wenkai",
        "family": "LXGW WenKai Screen",
        "src": os.path.join(WS7, r"hyperos_fonts\FontDump\system-fonts\MiSansVF_Overlay.ttf"),
        "face": None,
        "weight": "400",
    },
    {
        "name": "noto-serif",
        "family": "Noto Serif SC",
        "src": os.path.join(WS7, r"hyperos_fonts\FontDump\system-fonts\NotoSerifCJK-Regular.ttc"),
        "face": 2,
        "weight": "400",
    },
]


def load_font(src: str, face: int | None) -> TTFont:
    if src.lower().endswith(".ttc"):
        return TTCollection(src, lazy=False).fonts[face or 0]
    return TTFont(src, lazy=False)


def site_frequency() -> Counter:
    """统计站点内容里每个字符出现的次数 —— 用站点自己的语料当频次表，
    比通用字频表更贴合这个站。"""
    freq: Counter = Counter()
    patterns = [
        os.path.join(WEB, "src/content/docs/**/*.md"),
        os.path.join(WEB, "src/content/blog/**/*.md"),
        os.path.join(WEB, "src/**/*.astro"),
        os.path.join(WEB, "src/**/*.json"),
        os.path.join(WEB, "src/styles/*.css"),
        os.path.join(WEB, "astro.config.mjs"),
    ]
    for pat in patterns:
        for f in glob.glob(pat, recursive=True):
            try:
                t = open(f, encoding="utf-8").read()
            except OSError:
                continue
            freq.update(ch for ch in t if ord(ch) >= 0x80)
    return freq


def build_slices(cmap: dict, freq: Counter) -> list[str]:
    """把字体的全部字符划分成若干片，返回 unicode-range 字符串列表。"""
    all_cp = set(cmap)
    used = sorted((cp for cp in all_cp if chr(cp) in freq),
                  key=lambda cp: (-freq[chr(cp)], cp))
    rest = sorted(all_cp - set(used))

    groups: list[list[int]] = []
    for i in range(0, len(used), SITE_CHUNK):
        groups.append(used[i:i + SITE_CHUNK])
    for i in range(0, len(rest), REST_CHUNK):
        groups.append(rest[i:i + REST_CHUNK])

    def to_range(cps: list[int]) -> str:
        cps = sorted(cps)
        parts, start, prev = [], cps[0], cps[0]
        for cp in cps[1:]:
            if cp == prev + 1:
                prev = cp
                continue
            parts.append(f"U+{start:X}" if start == prev else f"U+{start:X}-{prev:X}")
            start = prev = cp
        parts.append(f"U+{start:X}" if start == prev else f"U+{start:X}-{prev:X}")
        return ", ".join(parts)

    return [to_range(g) for g in groups]


def slice_one(task: tuple) -> int:
    src, face, rng, dest = task
    font = load_font(src, face)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.notdef_outline = True
    sub = subset.Subsetter(options=opts)
    sub.populate(unicodes=parse_unicodes(rng))
    sub.subset(font)
    font.flavor = "woff2"
    font.save(dest)
    font.close()
    return os.path.getsize(dest)


def main() -> int:
    # 进程池在这台机器上会死锁（worker 建好后就不动了），改成「多个独立进程各切一片区」。
    # 用法：python tools/slice_fonts.py --shard 0 4
    shard, nshard = 0, 1
    if "--shard" in sys.argv:
        i = sys.argv.index("--shard")
        shard, nshard = int(sys.argv[i + 1]), int(sys.argv[i + 2])
    only_css = "--css-only" in sys.argv

    freq = site_frequency()
    print(f"站点字符（去重）：{len(freq)} 个")

    all_css: list[str] = [
        "/* 自动生成，请勿手改 —— 由 tools/slice_fonts.py 产出 */",
        "/* 分片是字体完整字符集的『划分』：每片覆盖一部分，合起来无遗漏、无重叠。",
        "   站点内容里出现的字被排在最前面几片，所以正常浏览只会下到 1～2 片。 */",
        "",
    ]

    for job in JOBS:
        if not os.path.exists(job["src"]):
            print(f"  ✗ {job['name']}：找不到 {job['src']}")
            continue

        font = load_font(job["src"], job["face"])
        cmap = font.getBestCmap()
        font.close()
        ranges = build_slices(cmap, freq)
        covered = set()
        for r in ranges:
            covered |= set(parse_unicodes(r))   # parse_unicodes 返回的是 list
        assert covered == set(cmap), "划分有遗漏！"
        print(f"\n{job['name']}：字体 {len(cmap)} 字 → {len(ranges)} 片，覆盖校验通过")

        outdir = os.path.join(OUT, job["name"])
        os.makedirs(outdir, exist_ok=True)
        # 注意：--css-only 绝不能走到这里删文件。
        # 之前没加这道判断，跑 --css-only 时把刚切好的 243 个分片全删了。
        if not only_css:
            for f in glob.glob(os.path.join(outdir, "*.woff2")):
                os.remove(f)

        tasks = [(job["src"], job["face"], rng, os.path.join(outdir, f"s{i}.woff2"))
                 for i, rng in enumerate(ranges)
                 if i % nshard == shard and not os.path.exists(
                     os.path.join(outdir, f"s{i}.woff2"))]
        t0 = time.time()
        total = 0
        if not only_css:
            for n, task in enumerate(tasks, 1):
                total += slice_one(task)
                if n % 5 == 0 or n == len(tasks):
                    print(f"    分片 {shard}/{nshard}：{n}/{len(tasks)} 片，"
                          f"{time.time() - t0:.0f}s", flush=True)
        print(f"  分片 {shard}/{nshard} 完成 {len(tasks)} 片"
              + (f"，{total / 1024 / 1024:.2f} MB" if total else ""))

        all_css.append(f"/* ---------- {job['family']} ---------- */")
        for i, rng in enumerate(ranges):
            all_css.append("@font-face {")
            all_css.append(f'  font-family: "{job["family"]}";')
            all_css.append(f'  src: url("/fonts/{job["name"]}/s{i}.woff2") format("woff2");')
            all_css.append(f"  font-weight: {job['weight']};")
            all_css.append("  font-style: normal;")
            all_css.append("  font-display: swap;")
            all_css.append(f"  unicode-range: {rng};")
            all_css.append("}")
        all_css.append("")

    if nshard > 1 and not only_css:
        print("\n分片模式：CSS 由主进程统一生成")
        return 0
    open(os.path.join(OUT, "sliced.css"), "w", encoding="utf-8").write("\n".join(all_css))
    print("\n已生成 public/fonts/sliced.css")
    return 0


if __name__ == "__main__":
    sys.exit(main())
