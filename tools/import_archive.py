#!/usr/bin/env python3
"""
import_archive.py — 把抓到的存档（浏览器另存的网页 / 下载的 zip / 散落的图片）
                    收拢进站点，并核对图片是否齐全。

三种用法可以混用：

  1) 解包浏览器端脚本下载的 zip
     python import_archive.py --zip fandom-archive.zip --xml dump/xxx.xml --into web/docs/assets/wiki-images

  2) 扫描若干文件夹（浏览器「另存为完整网页」生成的 html + _files 文件夹、下载目录等）
     python import_archive.py --from ~/Downloads wiki-pages --xml dump/xxx.xml --into web/docs/assets/wiki-images

  3) 只做核对，不复制
     python import_archive.py --from ~/Downloads --xml dump/xxx.xml --check-only
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


def expected_images(xml_path: str) -> set[str]:
    """从导出文件里取出所有 File: 页面，即该维基的全部图片文件名。

    导出里会登记一些缩略图变体（形如 `xxx.jpg@128w 128h 1c 1s.webp`），
    它们不是独立文件，这里去掉 @ 后缀再统计。
    """
    root = ET.parse(xml_path).getroot()
    names = set()
    for p in root.findall(NS + "page"):
        if p.findtext(NS + "ns") != "6":
            continue
        title = p.findtext(NS + "title") or ""
        if ":" in title:
            name = title.split(":", 1)[1]
            name = name.split("@", 1)[0].strip()
            if name:
                names.add(name)
    return names


def referenced_images(docs_dir: str) -> set[str]:
    """扫描已生成的 Markdown，找出站点真正引用到的图片文件名。"""
    names: set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(docs_dir):
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for m in re.finditer(r"wiki-images/([^)\"'\s]+)", text):
                names.add(urllib.parse.unquote(m.group(1)))
    return names


def normalize(name: str) -> str:
    """把浏览器可能加上的后缀、编码差异归一化，便于匹配。"""
    name = re.sub(r"\s*\(\d+\)(?=\.[^.]+$|$)", "", name)   # xxx (1).png → xxx.png
    name = name.replace("%20", " ").strip()
    return name


def collect_files(sources: list[str]) -> dict[str, str]:
    """扫描所有来源文件夹，返回 {归一化文件名: 实际路径}（先到先得）。"""
    found: dict[str, str] = {}
    for src in sources:
        src = os.path.expanduser(src)
        if not os.path.exists(src):
            print(f"  ! 跳过不存在的路径：{src}")
            continue
        if os.path.isfile(src):
            found.setdefault(normalize(os.path.basename(src)), src)
            continue
        for dirpath, _dirnames, filenames in os.walk(src):
            for fn in filenames:
                key = normalize(fn)
                found.setdefault(key, os.path.join(dirpath, fn))
    return found


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
    ap.add_argument("--docs", default=None, help="已生成的 docs/wiki 目录，用来核对站点实际引用的图片")
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
    print(f"  共发现 {len(found)} 个文件\n")

    hit = {name: found[name] for name in want if name in found}
    missing = sorted(want - set(hit))
    extra = sorted(set(found) - want)

    print(f"登记图片匹配：{len(hit)}/{len(want)}")

    # 站点真正引用的图片才是关键指标
    if args.docs and os.path.isdir(args.docs):
        refs = referenced_images(args.docs)
        ref_hit = sorted(r for r in refs if r in found)
        ref_missing = sorted(r for r in refs if r not in found)
        print(f"\n站点引用图片：{len(refs)} 张，已找到 {len(ref_hit)}，缺 {len(ref_missing)}")
        if ref_missing:
            print("  缺失清单：")
            for m in ref_missing[:25]:
                print(f"    - {m}")
            if len(ref_missing) > 25:
                print(f"    … 还有 {len(ref_missing) - 25} 张")
        else:
            print("  ✓ 站点用到的图片全都齐了")
        missing = ref_missing or missing

    if missing:
        print(f"\n仍缺 {len(missing)} 张（前 25 个）：")
        for m in missing[:25]:
            print(f"  - {m}")
    else:
        print("\n  ✓ 图片齐全")

    if extra:
        print(f"\n另有 {len(extra)} 个不在登记表里的文件（可能是缩略图或页面素材），例如：")
        for e in extra[:10]:
            print(f"  - {e}")

    if args.into and not args.check_only and hit:
        os.makedirs(args.into, exist_ok=True)
        copied = 0
        for name, path in hit.items():
            dest = os.path.join(args.into, name)
            if os.path.exists(dest) and os.path.getsize(dest) == os.path.getsize(path):
                continue
            shutil.copy2(path, dest)
            copied += 1
        print(f"\n已复制 {copied} 张到 {args.into}（其余已存在）")
        print("下一步：在 web 目录执行 mkdocs build 重新构建站点。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
