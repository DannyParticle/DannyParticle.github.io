#!/usr/bin/env python3
"""
process_avatar.py — 把用户给的图片处理成站点头像与站点图标。

- 居中裁成正方形（圆形头像不会切到主体）
- avatar.jpg  512×512，首页头像 + 顶栏 logo
- favicon.png  64×64，浏览器标签图标
"""
from __future__ import annotations

import os
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = sys.argv[1] if len(sys.argv) > 1 else None
PUBLIC = "wiki-migration/web/public"

if not SRC or not os.path.exists(SRC):
    raise SystemExit(f"找不到源图：{SRC}")

os.makedirs(PUBLIC, exist_ok=True)
im = Image.open(SRC).convert("RGB")
w, h = im.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
im = im.crop((left, top, left + side, top + side))
print(f"原图 {w}×{h} → 居中裁成 {side}×{side}")

avatar = im.resize((512, 512), Image.LANCZOS)
avatar.save(os.path.join(PUBLIC, "avatar.jpg"), "JPEG", quality=88, optimize=True,
            progressive=True)
print(f"头像  → public/avatar.jpg   512×512  "
      f"{os.path.getsize(os.path.join(PUBLIC, 'avatar.jpg'))/1024:.0f} KB")

fav = im.resize((64, 64), Image.LANCZOS)
fav.save(os.path.join(PUBLIC, "favicon.png"), "PNG", optimize=True)
print(f"图标  → public/favicon.png   64×64  "
      f"{os.path.getsize(os.path.join(PUBLIC, 'favicon.png'))/1024:.1f} KB")
