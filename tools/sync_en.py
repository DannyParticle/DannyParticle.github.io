#!/usr/bin/env python3
"""
sync_en.py —— 中文内容改了之后，自动同步英文版。

思路是「增量」而不是「重翻」：

  1. 清单 .en-sync.json 里同时记着上次同步时的**中文原文**和**英文译文**，
     这两份严格逐行对应（当初翻译时就保持了结构，同步过程也维持它）
  2. 用 difflib 把「上次的中文」和「这次的中文」逐行对齐
  3. 对齐上的行直接沿用清单里那行对应的英文 —— 人工质量的译文不动
  4. 只有新增/改动的行才送去翻译

**安全底线：任何情况下都不会把中文写进英文文件。**
如果英文与清单里的中文行数对不上（说明有人绕过同步改了中文），
就退化成「整篇重翻」并大声告警 —— 宁可质量降一档，也不能把中文混进去。

翻译接口：Google 免密钥接口优先（GitHub Actions 在海外能通），失败退到 MyMemory。
两个都失败就放弃本次同步并报错退出，绝不写入半截内容。

送翻前会把 HTML 标签、URL、行内代码、以及视频表格的「视频标题」列换成占位符，
翻完再还原 —— 否则接口会把标签链接一起搅坏，或者把标题也翻了。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.abspath(os.path.join(HERE, ".."))
MANIFEST = os.path.join(WEB, ".en-sync.json")

PAIRS = [
    ("src/content/docs/wiki", "src/content/docs/en/wiki"),
    ("src/content/blog", "src/content/blog-en"),
]

CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
FENCE = re.compile(r"^\s*(```|~~~)")
VIDEO_ROW = re.compile(r"^\|\s*\d{4}年")
UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
}


# ---------------------------------------------------------------- 翻译接口

def _google(texts: list[str]) -> list[str]:
    out = []
    for t in texts:
        q = urllib.parse.quote(t)
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl=zh-CN&tl=en&dt=t&q={q}")
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
        data = json.loads(raw)
        out.append("".join(seg[0] for seg in data[0] if seg and seg[0]))
        time.sleep(0.15)
    return out


def _mymemory(texts: list[str]) -> list[str]:
    out = []
    for t in texts:
        chunks = [t[i:i + 480] for i in range(0, len(t), 480)] or [t]
        parts = []
        for c in chunks:
            q = urllib.parse.quote(c)
            url = f"https://api.mymemory.translated.net/get?q={q}&langpair=zh-CN|en"
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
            parts.append(json.loads(raw)["responseData"]["translatedText"])
            time.sleep(0.35)
        out.append("".join(parts))
    return out


# 兜底用的严格保护表：把整个 Markdown 链接当一块，链接文字就不翻了，
# 但结构绝对不会坏。只有在宽松模式校验不过时才用。
STRICT_PATTERNS = [
    re.compile(r"<[^>]+>"),
    re.compile(r"!?\[[^\]]*\]\([^)]+\)"),
    re.compile(r"https?://\S+"),
    re.compile(r"`[^`]+`"),
    re.compile(r"\*\*[^*]+\*\*"),
    re.compile(r"\*[^*]+\*"),
]

PROVIDERS = [("google", _google), ("mymemory", _mymemory)]
FULL_MARK = "，整篇重翻"


def translate(texts: list[str], cache: dict[str, str]) -> tuple[list[str], str]:
    todo = [t for t in texts if t not in cache]
    used = "缓存"
    if todo:
        for name, fn in PROVIDERS:
            try:
                results = fn(todo)
                if len(results) != len(todo):
                    raise ValueError("返回条数对不上")
                for src, dst in zip(todo, results):
                    cache[src] = dst
                used = name
                break
            except Exception as e:  # noqa: BLE001
                print(f"    接口 {name} 失败：{type(e).__name__} {str(e)[:60]}")
        else:
            raise RuntimeError("所有翻译接口都不可用")
    return [cache[t] for t in texts], used


# ---------------------------------------------------------------- 占位符保护

PROTECT_PATTERNS = [
    re.compile(r"<[^>]+>"),                          # HTML 标签
    # 图片整块保护：alt 大多就是文件名，翻了反而错
    re.compile(r"!\[[^\]]*\]\([^)]+\)"),
    # 普通链接只保护 ](地址)，链接文字留给翻译 ——
    # 否则英文版里会冒出「[英文版](/en/wiki/)」这种中英混排
    re.compile(r"\]\([^)]+\)"),
    re.compile(r"https?://\S+"),                     # 裸 URL
    re.compile(r"`[^`]+`"),                          # 行内代码
    re.compile(r"\*\*[^*]+\*\*"),                    # 加粗
    re.compile(r"\*[^*]+\*"),                        # 斜体
]


def protect(line: str, patterns=None) -> tuple[str, list[str]]:
    saved: list[str] = []

    def stash(m: re.Match) -> str:
        saved.append(m.group(0))
        # 实测：⟦0⟧ 这种会被接口拆开，{0} 能原样保留
        return "{" + str(len(saved) - 1) + "}"

    out = line
    for pat in (patterns or PROTECT_PATTERNS):
        out = pat.sub(stash, out)
    return out, saved


def restore(text: str, saved: list[str]) -> str:
    def put(m: re.Match) -> str:
        i = int(m.group(1))
        return saved[i] if 0 <= i < len(saved) else m.group(0)

    return re.sub(r"\{\s*(\d+)\s*\}", put, text)


def prepare(line: str, strict: bool = False) -> str:
    """把一行变成「可送翻文本 + 保护内容」。"""
    body = line
    title = None
    if VIDEO_ROW.match(line.strip()):
        cells = line.split("|")
        if len(cells) >= 4:
            title = cells[2]
            cells[2] = " {T} "
            body = "|".join(cells)
    protected, saved = protect(body, STRICT_PATTERNS if strict else None)
    if title is not None:
        saved.append(title)
        protected = protected.replace("{T}", "{" + str(len(saved) - 1) + "}")
    return protected + "\x01" + json.dumps(saved, ensure_ascii=False)


LEAK = re.compile(r"\{\s*\d+\s*\}")


def finish(payload: str, translated: str) -> str:
    saved = json.loads(payload.split("\x01", 1)[1])
    out = restore(translated, saved)
    if LEAK.search(out):
        # 接口把占位符拆坏了 —— 与其留个 {0} 在页面上，不如退回中文原文，
        # 至少内容是对的，而且下一次同步会再试一遍
        raise PlaceholderLeak(out)
    return out


class PlaceholderLeak(RuntimeError):
    pass


def translatable(line: str, in_fence: bool) -> bool:
    if in_fence:
        return False
    s = line.strip()
    if not s or not CJK.search(line):
        return False
    if s in ("---", "***", "___"):
        return False
    if re.fullmatch(r"</?[a-zA-Z][^>]*>", s):
        return False
    return True


# ---------------------------------------------------------------- 同步

def translate_block(new_lines: list[str], cache: dict) -> tuple[list[str], int]:
    """翻译一段中文行（跳过代码块与无中文的行）。"""
    out: list[str] = []
    payloads: list[str] = []
    slots: list[int] = []
    in_fence = False
    for line in new_lines:
        fence_line = bool(FENCE.match(line))
        if translatable(line, in_fence):
            out.append("\x00")
            slots.append(len(out) - 1)
            payloads.append(prepare(line))
        else:
            out.append(line)
        if fence_line:
            in_fence = not in_fence

    if payloads:
        results, used = translate([p.split("\x01", 1)[0] for p in payloads], cache)
        retry: list[int] = []
        for k, (slot, res, p) in enumerate(zip(slots, results, payloads)):
            out[slot] = finish(p, res)
            # 括号结构对不上就说明接口把链接拆坏了，退回严格模式重来
            src_line = new_lines[slot]
            if (out[slot].count("[") != src_line.count("[")
                    or out[slot].count("]") != src_line.count("]")):
                retry.append(k)
        if retry:
            print(f"    {len(retry)} 行链接结构被拆坏，用严格模式重试")
            strict_payloads = [prepare(new_lines[slots[k]], strict=True) for k in retry]
            # 注意：这里刻意用一个空缓存，否则会命中刚才那版坏结果
            strict_results, _ = translate(
                [p.split("\x01", 1)[0] for p in strict_payloads], {})
            for k, p, res in zip(retry, strict_payloads, strict_results):
                out[slots[k]] = finish(p, res)
        print(f"    用 {used} 翻译了 {len(payloads)} 行")
    return out, len(payloads)


def sync_file(zh_rel: str, en_rel: str, manifest: dict, cache: dict,
              force: bool) -> tuple[str, int, bool]:
    """返回 (状态, 新翻行数, 是否整篇重翻)。"""
    zh_path = os.path.join(WEB, zh_rel)
    en_path = os.path.join(WEB, en_rel)
    if not os.path.exists(zh_path):
        return "源文件不存在", 0, False

    zh_now = open(zh_path, encoding="utf-8").read()
    zh_hash = hashlib.sha1(zh_now.encode()).hexdigest()
    rec = manifest["files"].get(zh_rel)

    if rec and rec.get("hash") == zh_hash and os.path.exists(en_path) and not force:
        return "无变化", 0, False

    zh_old = rec.get("zh", "") if rec else ""
    en_old = rec.get("en_text", "") if rec else ""
    en_now = open(en_path, encoding="utf-8").read() if os.path.exists(en_path) else ""

    old_lines = zh_old.split("\n")
    new_lines = zh_now.split("\n")
    # 优先用清单里记着的英文（与清单里的中文严格对应），没有才退回磁盘
    src_en = en_old or en_now
    en_lines = src_en.split("\n") if src_en else []

    whole = False
    if not en_lines:
        whole = True                                  # 全新文件
    elif len(en_lines) != len(old_lines):
        whole = True                                  # 对不齐，只能整篇重翻
        print(f"    ⚠ 英文 {len(en_lines)} 行 ≠ 基线中文 {len(old_lines)} 行，"
              f"整篇重翻（不会写入中文）")

    if whole:
        en_out, n = translate_block(new_lines, cache)
    else:
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        en_out = []
        n = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                en_out.extend(en_lines[i1:i2])
            else:
                block, used = translate_block(new_lines[j1:j2], cache)
                en_out.extend(block)
                n += used

    new_en = "\n".join(en_out)
    if not new_en.strip():
        raise RuntimeError("生成的英文为空，放弃")

    if new_en != en_now:
        os.makedirs(os.path.dirname(en_path), exist_ok=True)
        open(en_path, "w", encoding="utf-8").write(new_en)

    manifest["files"][zh_rel] = {
        "hash": zh_hash, "zh": zh_now, "en": en_rel, "en_text": new_en,
    }
    return ("已更新" if new_en != en_now else "无变化"), n, whole


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="忽略哈希，全部重算")
    ap.add_argument("--dry-run", action="store_true", help="只报告哪些文件会变")
    ap.add_argument("--init", action="store_true",
                    help="把当前中英对照记为基线，不翻译（首次接入时用）")
    args = ap.parse_args()

    manifest = {"files": {}, "cache": {}}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST, encoding="utf-8"))
        manifest.setdefault("files", {})
        manifest.setdefault("cache", {})
    cache = manifest["cache"]

    targets: list[tuple[str, str]] = []
    for zh_dir, en_dir in PAIRS:
        for root, _dirs, files in os.walk(os.path.join(WEB, zh_dir)):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(root, fn), WEB).replace("\\", "/")
                targets.append((rel, rel.replace(zh_dir, en_dir, 1)))

    if args.init:
        for zh_rel, en_rel in targets:
            zh_now = open(os.path.join(WEB, zh_rel), encoding="utf-8").read()
            en_path = os.path.join(WEB, en_rel)
            en_now = open(en_path, encoding="utf-8").read() if os.path.exists(en_path) else ""
            manifest["files"][zh_rel] = {
                "hash": hashlib.sha1(zh_now.encode()).hexdigest(),
                "zh": zh_now, "en": en_rel, "en_text": en_now,
            }
        json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print(f"已把 {len(targets)} 个文件的当前状态记为基线（未做任何翻译）")
        return 0

    print(f"检查 {len(targets)} 个文件")
    changed = lines = wholes = 0
    for zh_rel, en_rel in targets:
        rec = manifest["files"].get(zh_rel)
        zh_now = open(os.path.join(WEB, zh_rel), encoding="utf-8").read()
        if rec and rec.get("hash") == hashlib.sha1(zh_now.encode()).hexdigest() and not args.force:
            continue
        print(f"  {zh_rel}")
        if args.dry_run:
            changed += 1
            continue
        try:
            status, n, whole = sync_file(zh_rel, en_rel, manifest, cache, args.force)
        except Exception as e:  # noqa: BLE001
            print(f"    ✗ 同步失败：{type(e).__name__}: {str(e)[:90]}")
            return 1        # 宁可整体失败，也不写入半截内容
        print(f"    {status}（新翻 {n} 行{FULL_MARK if whole else ''}）")
        if status == "已更新":
            changed += 1
            lines += n
            wholes += 1 if whole else 0

    if not args.dry_run:
        json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\n{'将更新' if args.dry_run else '已更新'} {changed} 个文件，"
          f"新翻 {lines} 行" + (f"，其中 {wholes} 个整篇重翻" if wholes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
