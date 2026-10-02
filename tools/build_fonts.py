#!/usr/bin/env python3
"""
build_fonts.py —— 准备站点的中文字体。

**不使用 unicode-range 分片**：分片虽然省流量，但一旦某个字不在分片覆盖范围内
就会掉到后备字体，看起来像「缺字」。这里每个字族只放一个完整字体文件，
新增内容永远有字可用。

许可差异决定了输出格式：

  霞鹜文楷屏幕阅读版 / 思源宋体   SIL OFL 1.1 —— 允许修改，转成 woff2（约省一半）
  MiSans / HarmonyOS Sans         厂商自有许可，明文「不得修改」
                                  → 原样输出 TTF，只做拷贝，不做任何再编码

原文件在工作区留一份（--keep 指定的目录），发布用的放在 public/fonts/。
"""
from __future__ import annotations

import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fontTools.ttLib import TTCollection, TTFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.abspath(os.path.join(HERE, ".."))
WS7 = r"C:\Users\李自远\Documents\deepseekharness\ws7"
HARMONY = os.path.join(os.environ["TEMP"], "fontdl", "harmony", "HarmonyOS Sans", "HarmonyOS_Sans_SC")

OUT = os.path.join(WEB, "public", "fonts")
KEEP = os.path.abspath(os.path.join(WEB, "..", "fonts"))     # 工作区留档

# name, 源文件, 输出文件名, 是否转 woff2, TTC 里的面序号, 许可
FONTS = [
    ("wenkai-screen", os.path.join(WS7, r"hyperos_fonts\FontDump\system-fonts\MiSansVF_Overlay.ttf"),
     "LXGWWenKaiScreen.ttf", True, None, "SIL OFL 1.1"),
    ("noto-serif-sc", os.path.join(WS7, r"hyperos_fonts\FontDump\system-fonts\NotoSerifCJK-Regular.ttc"),
     "NotoSerifSC-Regular.otf", True, 2, "SIL OFL 1.1"),
    ("misans", os.path.join(WS7, r"hyperos_fonts\FontDump\product-fonts\MiSansVF.ttf"),
     "MiSansVF.ttf", False, None, "Xiaomi MiSans License"),
    ("harmonyos-sc", os.path.join(HARMONY, "HarmonyOS_Sans_SC_Regular.ttf"),
     "HarmonyOS_Sans_SC_Regular.ttf", False, None, "HarmonyOS Sans Fonts License"),
]


def load(path: str, face: int | None):
    if path.lower().endswith(".ttc"):
        return TTCollection(path, lazy=False).fonts[face or 0]
    return TTFont(path, lazy=False)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    total = 0

    for key, src, out_name, to_woff2, face, lic in FONTS:
        if not os.path.exists(src):
            print(f"  ✗ {key}: 找不到 {src}")
            continue

        src_mb = os.path.getsize(src) / 1024 / 1024

        # 1) 工作区留档：原文件原样拷一份
        kept = os.path.join(KEEP, f"{key}__{os.path.basename(src)}")
        if not os.path.exists(kept) or os.path.getsize(kept) != os.path.getsize(src):
            shutil.copy2(src, kept)

        # 2) 发布用的
        dest_name = out_name.replace(".ttf", ".woff2").replace(".otf", ".woff2") if to_woff2 else out_name
        dest = os.path.join(OUT, dest_name)

        if to_woff2:
            font = load(src, face)
            font.flavor = "woff2"
            font.save(dest)
            font.close()
        else:
            # 厂商许可禁止修改 —— 原样拷贝，一个字节都不动
            if not os.path.exists(dest) or os.path.getsize(dest) != os.path.getsize(src):
                shutil.copy2(src, dest)

        dest_mb = os.path.getsize(dest) / 1024 / 1024
        total += dest_mb
        fmt = "woff2" if to_woff2 else "ttf(原样)"
        ratio = f"{dest_mb / src_mb * 100:.0f}%" if to_woff2 else "100%"
        print(f"  {key:<15} {src_mb:6.1f}MB → {dest_mb:6.1f}MB ({ratio:>4})  {fmt:<10} {lic}")
        print(f"                  留档 {os.path.relpath(kept, os.path.dirname(KEEP))}")

    print(f"\n发布用字体合计：{total:.1f} MB → {os.path.relpath(OUT, WEB)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
