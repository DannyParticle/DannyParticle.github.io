#!/usr/bin/env python3
"""
rebuild_videolist.py —— 把 channel.md 里那张 175 行的 HTML 大表，
重排成「按年份折叠 + Markdown 表格 + 标题即链接」的结构。

为什么要改：
  · 编辑困难 —— 一张 175 行的 HTML 表塞在文本框里，找一行要滚半天
  · 没有年份分组
  · 视频链接没地方放

改完的结构：

    <details>展开查看
      <div>主要内容</div>
      <details>2022 年（1 个）</details>
      <details>2023 年（41 个）</details>
      ... 2026 年不折叠，直接铺开
      <div>不器</div>
      不器的表
    </details>

数据来源是**当前的 channel.md**（不是原始 XML）—— 上面有手工补充的内容，
重新从 XML 生成会把它们冲掉。链接来自 tools/match_bili.py 的匹配结果。
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import OrderedDict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "..", "src", "content", "docs", "wiki", "channel.md")
MATCHES = os.path.join(HERE, "..", "bili-matches.json")

# 只有「纯粹就是个链接」的备注，在标题已经带上链接之后就没必要重复了
PLACEHOLDER_LINK = re.compile(r"^\s*(?:是?动态视频)?\s*[（(]\s*(?:此|这)(?:为|是)?链接\s*[）)]?\s*$")


def cell(text: str) -> str:
    """把一段文本放进 Markdown 表格单元格。

    标题里常有 `｜` 或 `|` 做分隔符；半角的 `|` 在表格里是列分隔符，
    会被解析器切断，所以统一换成全角的 `｜`（中文排版本来也更该用它）。
    """
    text = text.replace("|", "｜")
    text = re.sub(r"\s*\n\s*", " ", text).strip()
    return text or " "


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def md_link_to_html(s: str) -> str:
    """把 [文字](地址) 转成 <a>。

    分组标题是包在 <div> 里的，而 HTML 块里的 Markdown 不会被解析 ——
    直接写 Markdown 链接会原样显示出方括号，必须给成真 HTML。
    """
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)


def parse_rows(text: str) -> tuple[list[dict], str, str]:
    """把 HTML 表格解析成结构化数据。

    返回 (条目列表, 表格前的文字, 表格后的文字)。
    条目形如 {group, date, title, cat, note}
    """
    start = text.find('<table class="wiki-table">')
    end = text.find("</table>", start)
    if start < 0 or end < 0:
        raise SystemExit("找不到视频表格")
    table = text[start:end + len("</table>")]

    items: list[dict] = []
    group = ""
    for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        # 分组标题行
        g = re.search(r'<td colspan="4">(.*?)</td>', tr, re.S)
        if g:
            group = strip_tags(g.group(1))
            continue

        # 数据行：两种形状
        #   主要内容：date / title / cat / note
        #   不器：    date / title(colspan=2) / note
        m4 = re.search(
            r'<td class="wiki-col-date">(.*?)</td>'
            r'<td class="wiki-col-title">(.*?)</td>'
            r'<td class="wiki-col-cat">(.*?)</td>'
            r'<td class="wiki-col-note">(.*?)</td>', tr, re.S)
        m3 = re.search(
            r'<td class="wiki-col-date">(.*?)</td>'
            r'<td colspan="2">(.*?)</td>'
            r'<td class="wiki-col-note">(.*?)</td>', tr, re.S)

        if m4:
            date, title, cat, note = (x.strip() for x in m4.groups())
        elif m3:
            date, title, note = (x.strip() for x in m3.groups())
            cat = ""
        else:
            continue
        if not date or not title:
            continue
        items.append({"group": group, "date": date, "title": title,
                      "cat": cat, "note": note})

    return items, text[:start], text[end + len("</table>"):]


def year_of(date: str) -> str:
    m = re.match(r"(\d{4})", date)
    return m.group(1) if m else "未知"


NOTE_URL = re.compile(r"\]\((https?://(?:www\.)?bilibili\.com/video/[^)]+)\)")


def link_for(item: dict, matches: list[dict]) -> str | None:
    """给这一行找视频链接。

    优先用投稿列表匹配出来的；匹配不上就退回备注里原本写着的链接
    —— 有 8 条不在主号投稿列表里（工作室另一个号发的，或互动视频）。
    """
    for r in matches:
        if r["date"] == item["date"] and strip_tags(r["title"]) == strip_tags(item["title"]):
            if r.get("bvid"):
                return f"https://www.bilibili.com/video/{r['bvid']}/"
    m = NOTE_URL.search(item["note"])
    return m.group(1) if m else None


def render_table(items: list[dict], matches: list[dict], with_cat: bool) -> str:
    if with_cat:
        head = "| 发布 | 视频标题 | 所属系列 | 备注 |\n|---|---|---|---|"
    else:
        head = "| 发布 | 视频标题 | 备注 |\n|---|---|---|"

    lines = [head]
    linked = 0
    for it in items:
        title = cell(it["title"])
        url = link_for(it, matches)
        if url:
            title = f"[{title}]({url})"
            linked += 1
        note = it["note"]
        # 备注里如果只是一句「（这是链接）」占位，标题有链接后就多余了
        if url and PLACEHOLDER_LINK.match(strip_tags(note).replace("|", "")):
            note = ""
        cells = [cell(it["date"]), title]
        if with_cat:
            cells.append(cell(it["cat"]))
        cells.append(cell(note))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines), linked


def main() -> int:
    # --out 可以写到别处，方便先干跑看效果
    out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else MD
    text = open(MD, encoding="utf-8").read()
    items, before, after_raw = parse_rows(text)

    # before 里已经有一份 `## 视频列表` 标题和 <details><summary>展开查看</summary> 外壳，
    # 我们要重建这一段，所以从标题处截断。
    head = before.rfind("## 视频列表")
    before = before[:head] if head >= 0 else before
    # 表格后面紧跟的原外壳 </details> 也要去掉，只保留后面的「附：」等内容
    after = re.sub(r"^\s*</details>\s*", "", after_raw, count=1)

    print(f"解析出 {len(items)} 条视频")

    matches = []
    if os.path.exists(MATCHES):
        matches = json.load(open(MATCHES, encoding="utf-8"))
        n = sum(1 for m in matches if m.get("bvid"))
        print(f"载入匹配结果 {len(matches)} 条（其中 {n} 条有链接）")
    else:
        print("没有匹配结果，链接留空（之后可重跑 tools/match_bili.py）")

    # 按 group → year 归拢，保持原有顺序
    groups: "OrderedDict[str, OrderedDict[str, list[dict]]]" = OrderedDict()
    for it in items:
        groups.setdefault(it["group"], OrderedDict()).setdefault(year_of(it["date"]), []).append(it)

    out = [before.rstrip("\n"), "", "## 视频列表", ""]
    out.append("<details>")
    out.append("<summary>展开查看</summary>")
    out.append("")
    out.append("按年份折叠，点年份展开。当年的不折叠，直接铺开。")
    out.append("")

    total_linked = 0
    for gi, (group, years) in enumerate(groups.items()):
        total = sum(len(v) for v in years.values())
        # 不器那几个条目按系列分组（没有「所属系列」这一列）
        with_cat = "不器" not in group
        # 条目太少就不值得再按年折叠
        fold = total > 10

        if gi:
            out.append("")
        out.append(f'<div class="video-group">{md_link_to_html(group)}</div>')
        out.append("")

        if not fold:
            rows = [r for y in sorted(years) for r in years[y]]
            table, linked = render_table(rows, matches, with_cat)
            total_linked += linked
            out.append(table)
            out.append("")
            continue

        newest = max(years.keys())
        for year in sorted(years):
            rows = years[year]
            table, linked = render_table(rows, matches, with_cat)
            total_linked += linked
            if year == newest:
                # 最新一年不折叠
                out.append(f"**{year} 年**（{len(rows)} 个）")
                out.append("")
                out.append(table)
                out.append("")
            else:
                out.append("<details>")
                out.append(f"<summary>{year} 年（{len(rows)} 个）</summary>")
                out.append("")
                out.append(table)
                out.append("")
                out.append("</details>")
                out.append("")

    out.append("</details>")
    out.append("")
    new_text = "\n".join(out).rstrip("\n") + "\n\n" + after.lstrip("\n")

    open(out_path, "w", encoding="utf-8").write(new_text)
    print(f"已写入 {out_path}")
    print(f"  分组：{list(groups.keys())}")
    for g, ys in groups.items():
        print(f"    {g}: " + "、".join(f"{y}({len(v)})" for y, v in sorted(ys.items())))
    print(f"  标题带链接：{total_linked} 条")
    print(f"  文件：{len(text)} → {len(new_text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
