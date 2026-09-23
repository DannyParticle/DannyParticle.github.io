#!/usr/bin/env python3
"""
import_archive.py — 把抓到的存档（浏览器另存的网页 / 下载的 zip / 散落的图片）
                    收拢进站点，并核对图片是否齐全。

三种用法可以混用：

  1) 解包浏览器端脚本下载的 zip
     python import_archive.py --zip fandom-archive.zip --xml dump/xxx.xml \\
            --docs web/docs/wiki --into web/docs/assets/wiki-images

  2) 扫描若干文件夹（浏览器「另存为完整网页」生成的 html + _files 文件夹、下载目录等）
     python import_archive.py --from 网页 --xml dump/xxx.xml \\
            --docs web/docs/wiki --into web/docs/assets/wiki-images

  3) 只做核对，不复制
     python import_archive.py --from 网页 --xml dump/xxx.xml --check-only

名称匹配：浏览器另存时会把中文变成 %3F、把 png 存成 webp 缩略图、重名加 (1) 后缀，
这里统一归一化后再匹配；同一张图有多个副本时取体积最大的那个。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://www.mediawiki.org/xml/export-0.11/}"
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"}


def expected_images(xml_path: str) -> set[str]:
    """从导出文件里取出所有 File: 页面，即该维基的全部图片文件名。

    导出里会登记一些缩略图变体（形如 `xxx.jpg@128w 128h 1c 1s.webp`），
    它们不是独立文件，这里去掉 @ 后缀再统计。
    """
    root = ET.parse(xml_path).getroot()
    names: set[str] = set()
    for p in root.findall(NS + "page"):
        if p.findtext(NS + "ns") != "6":
            continue
        title = p.findtext(NS + "title") or ""
        if ":" in title:
            name = title.split(":", 1)[1].split("@", 1)[0].strip()
            if name:
                names.add(name)
    return names


def match_key(name: str) -> str:
    """生成用于宽松匹配的键。

    - 去掉扩展名（Fandom 把 png 存成 webp 缩略图）
    - %3F / ? （中文被转义后的残留）与所有非 ASCII 字符都折成通配符
    - 去掉浏览器加的 (1) (2) 后缀
    - 下划线视作空格（MediaWiki 把标题里的空格存成下划线，浏览器又可能反过来）
    """
    base = os.path.splitext(name)[0]
    base = urllib.parse.unquote(base)
    base = re.sub(r"\s*\(\d+\)$", "", base)
    base = base.replace("_", " ").replace("%20", " ")
    base = re.sub(r"[^\x00-\x7f]+", "*", base)
    base = base.replace("?", "*")
    base = re.sub(r"\*+", "*", base)
    return re.sub(r"\s+", " ", base).strip().lower()


def referenced_images(docs_dir: str) -> set[str]:
    """扫描已生成的 Markdown，找出站点真正引用到的图片文件名。

    图片既可能出现在 HTML 的 src="..." 里，也可能在 Markdown 的 ![](...) 里，
    文件名还可能含空格（例如 Screenshot 2025-09-17 120424.png），两种都要照顾。
    """
    names: set[str] = set()
    patterns = [r'src="([^"]*wiki-images/[^"]+)"', r"!\[[^\]]*\]\(([^)\s]*wiki-images/[^)]+)\)"]
    for dirpath, _dirnames, filenames in os.walk(docs_dir):
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for pat in patterns:
                for m in re.finditer(pat, text):
                    names.add(urllib.parse.unquote(m.group(1).split("wiki-images/", 1)[1]))
    return names


def collect_files(sources: list[str]) -> dict[str, str]:
    """扫描来源文件夹，返回 {匹配键: 体积最大的那个文件路径}。"""
    best: dict[str, tuple[int, str]] = {}
    scanned = 0
    for src in sources:
        src = os.path.expanduser(src)
        if not os.path.exists(src):
            print(f"  ! 跳过不存在的路径：{src}")
            continue
        if os.path.isfile(src):
            candidates = [src]
        else:
            candidates = []
            for dirpath, _dirnames, filenames in os.walk(src):
                candidates += [os.path.join(dirpath, fn) for fn in filenames]
        for path in candidates:
            if os.path.splitext(path)[1].lower() not in IMG_EXT:
                continue
            scanned += 1
            key = match_key(os.path.basename(path))
            size = os.path.getsize(path)
            if key not in best or size > best[key][0]:
                best[key] = (size, path)
    print(f"  扫描了 {scanned} 个图片文件，归并出 {len(best)} 个不同的匹配键")
    return {k: v[1] for k, v in best.items()}


def extract_zip(zip_path: str, dest: str) -> int:
    if not os.path.exists(zip_path):
        print(f"  ! 找不到 zip：{zip_path}")
        return 0
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
        n = len(zf.namelist())
    print(f"  已解包 {zip_path} → {dest}（{n} 个条目）")
    return n


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", action="append", default=[], help="浏览器脚本下载的 zip（可多次指定）")
    ap.add_argument("--from", dest="sources", action="append", default=[],
                    help="要扫描的文件夹或文件（可多次指定）")
    ap.add_argument("--xml", required=True, help="导出 XML，用来知道应该有多少张图片")
    ap.add_argument("--docs", default=None, help="已生成的 docs/wiki，用来核对站点实际引用的图片")
    ap.add_argument("--into", default=None, help="图片复制到哪（通常是 web/docs/assets/wiki-images）")
    ap.add_argument("--unzip-to", default=None, help="zip 解包位置，默认与 zip 同目录同名文件夹")
    ap.add_argument("--check-only", action="store_true", help="只核对，不复制")
    args = ap.parse_args()

    want = expected_images(args.xml)
    print(f"导出文件里登记了 {len(want)} 张图片\n")

    sources = list(args.sources)
    for zp in args.zip:
        dest = args.unzip_to or os.path.splitext(zp)[0]
        extract_zip(zp, dest)
        sources.append(dest)

    if not sources:
        print("没有指定 --zip 或 --from，无事可做。")
        return 0

    print(f"扫描 {len(sources)} 个来源…")
    found = collect_files(sources)

    # 期望名 → 实际文件；实际文件名保留原扩展名（webp 就存 webp）
    hit: dict[str, str] = {}
    for name in sorted(want):
        path = found.get(match_key(name))
        if path:
            stem = os.path.splitext(name)[0]
            ext = os.path.splitext(path)[1].lower()
            hit[name] = path if ext == os.path.splitext(name)[1].lower() else stem + ext

    missing = sorted(want - set(hit))
    print(f"\n登记图片匹配：{len(hit)}/{len(want)}")

    if args.docs and os.path.isdir(args.docs):
        refs = referenced_images(args.docs)
        ref_ok = sorted(r for r in refs
                        if r in hit or match_key(r) in {match_key(v) for v in hit.values()})
        ref_missing = sorted(r for r in refs if r not in ref_ok)
        print(f"站点引用图片：{len(refs)} 张，已找到 {len(ref_ok)}，缺 {len(ref_missing)}")
        if ref_missing:
            for m in ref_missing[:20]:
                print(f"    - {m}")
            if len(ref_missing) > 20:
                print(f"    … 还有 {len(ref_missing) - 20} 张")
        else:
            print("  ✓ 站点用到的图片全都齐了")
        missing = ref_missing or missing

    if missing:
        print(f"\n仍缺 {len(missing)} 张（前 20 个）：")
        for m in missing[:20]:
            print(f"  - {m}")
    else:
        print("\n  ✓ 图片齐全")

    if args.into and not args.check_only and hit:
        os.makedirs(args.into, exist_ok=True)
        copied = upgraded = kept = 0
        for name, dest_name in hit.items():
            src = found[match_key(name)]
            dest = os.path.join(args.into, os.path.basename(dest_name))
            if os.path.exists(dest):
                if os.path.getsize(src) > os.path.getsize(dest):
                    shutil.copy2(src, dest)
                    upgraded += 1
                else:
                    kept += 1
                continue
            shutil.copy2(src, dest)
            copied += 1
        print(f"\n已写入 {args.into}：新增 {copied}，更新为更清晰的版本 {upgraded}，"
              f"保持原样 {kept}")
        print("下一步：在 web 目录执行 mkdocs build 重新构建站点。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
