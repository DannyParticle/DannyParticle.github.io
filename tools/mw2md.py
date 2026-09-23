#!/usr/bin/env python3
"""
mw2md.py — 把 MediaWiki 导出（XML）转换成 MkDocs 用的 Markdown。

用法：
    python mw2md.py --xml dump.xml --docs ../../docs/wiki --report report.md
                    [--images ../fandom-archive/images]

处理内容：
    {{信息框}}        → HTML 信息卡（含图片画廊）
    {| 表格 |}        → Markdown 表格（有合并单元格时用 HTML）
    [[页面|文字]]     → [文字](相对路径.md)
    [[分类:X]]        → front matter 里的 tags
    [[文件:X.png|..]] → ![说明](assets/wiki-images/X.png)
    ''斜体'' '''粗体''' → *斜体* **粗体**
    == 标题 ==        → ## 标题
    <nowiki>/<ref>   → 原样保留 / 丢弃
    -{zh-hans:..;}-   → 取简体
"""
from __future__ import annotations

import argparse
import glob
import html as H
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

MW_NS = "{http://www.mediawiki.org/xml/export-0.11/}"

# --------------------------------------------------------------------------- #
# 页面 → 输出路径（docs/wiki 下的相对路径，不含 .md）
# --------------------------------------------------------------------------- #
PAGE_SLUGS: dict[str, str] = {
    "首页": "index",
    "王维诗里的MBTI Wiki": "about",
    "王维诗里的MBTI": "channel",
    "荣格理论和荣格八维": "theory/jung-eight-functions",
    "各mbti的排列组合（两人一组）": "pairings",
    "不器": "works/buqi",
    "王维诗里的MBTI-B站二创（有代表性）": "works/bilibili-fanworks",
    "王维诗里的工作室": "studio",
    "王元元": "people/wangyuanyuan",
    "维基": "people/viki",
    "云中鹿饮溪": "people/yunzhongluyinxi",
    "狐狸刷刷": "people/hulishuashua",
    "骨哥说": "people/guge",
    # 16 位角色
    "胡紫（INTJ）": "characters/huzi-intj",
    "舒迢（INTP）": "characters/shutiao-intp",
    "吕强人（ENTJ）": "characters/lvqiangren-entj",
    "郭哲梅（ENTP）": "characters/guozhemei-entp",
    "百里透黑（INFJ）": "characters/bailitouhei-infj",
    "萧福叠（INFP）": "characters/xiaofudie-infp",
    "苏达简（ENFJ）": "characters/sudajian-enfj",
    "修勾勾（ENFP）": "characters/xiugougou-enfp",
    "郝瑟（ISTJ）": "characters/haose-istj",
    "马麻（ISFJ）": "characters/mama-isfj",
    "池梓（ESTJ）": "characters/chizi-estj",
    "单歌（ESFJ）": "characters/shange-esfj",
    "祖安（ISTP）": "characters/zuan-istp",
    "柳怜（ISFP）": "characters/liulian-isfp",
    "莫竞（ESTP）": "characters/mojing-estp",
    "崔崔（ESFP）": "characters/cuicui-esfp",
}

# 信息框参数 → 中文标签（未列出的直接用参数名）
LABELS = {
    "title1": None, "title": None, "image1": "图片", "image": "图片",
    "介绍": "简介", "原名": "原名", "花名": "花名", "配音演员": "配音",
    "性别": "性别", "籍贯": "籍贯", "人格类型": "人格类型",
    "粉丝数": "粉丝数", "运营者": "运营者", "所在地": "所在地",
    "口号/宣传语": "宣传语", "首个视频发布时间": "首个视频", "网站": "链接",
    "基本信息": None,
}

INFOBOX_TEMPLATES = {"MBTI", "王维1", "王元元维基", "角色", "人物", "信息框"}
DROP_TEMPLATES = {
    "Stub", " stub", "T", "T/doc", "T/piece", "Navbox", "Mbox", "Hatnote", "Quote",
    "Current time", "UTC", "Documentation", "Documentation/doc", "From Wikipedia",
    "CC BY-SA 3.0", "Fairuse", "Other free", "Permission", "PD", "Self", "Tocright",
    "New article box", "DEFAULTSORT", "DISPLAYTITLE",
}

GALLERY_CSS_CLASS = "wiki-gallery"


# --------------------------------------------------------------------------- #
# 通用小工具
# --------------------------------------------------------------------------- #
def split_top_level(s: str, sep: str = "|") -> list[str]:
    """按 sep 切分，但忽略 {{ }}、[[ ]]、{| |}、<gallery> 内部的 sep。"""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_gallery = 0
    i = 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("{{", "[[", "{|"):
            depth += 1
            buf.append(two)
            i += 2
            continue
        if two in ("}}", "]]", "|}"):
            depth = max(0, depth - 1)
            buf.append(two)
            i += 2
            continue
        low = s[i:i + 9].lower()
        if low == "<gallery>":
            in_gallery += 1
            buf.append(s[i:i + 9])
            i += 9
            continue
        if s[i:i + 10].lower() == "</gallery>":
            in_gallery = max(0, in_gallery - 1)
            buf.append(s[i:i + 10])
            i += 10
            continue
        if s[i] == sep and depth == 0 and in_gallery == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(s[i])
        i += 1
    parts.append("".join(buf))
    return parts


def find_blocks(text: str, open_tok: str, close_tok: str) -> list[tuple[int, int]]:
    """找出成对记号的位置区间（支持嵌套）。"""
    spans: list[tuple[int, int]] = []
    i = 0
    while True:
        start = text.find(open_tok, i)
        if start < 0:
            break
        depth = 0
        j = start
        while j < len(text):
            if text.startswith(open_tok, j):
                depth += 1
                j += len(open_tok)
                continue
            if text.startswith(close_tok, j):
                depth -= 1
                j += len(close_tok)
                if depth == 0:
                    break
                continue
            j += 1
        spans.append((start, j))
        i = max(j, start + 1)
    return spans


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def slugify_fallback(title: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", title).strip(" .-")
    return s or "page"


# --------------------------------------------------------------------------- #
# 转换器
# --------------------------------------------------------------------------- #
class Converter:
    def __init__(self, slug_map: dict[str, str], image_names: set[str], images_url_prefix: str):
        self.slug_map = slug_map
        self.image_names = image_names
        self.images_url_prefix = images_url_prefix
        self.placeholders: list[str] = []
        self.tags: list[str] = []
        self.dropped_templates: dict[str, int] = {}
        self.unknown_links: set[str] = set()
        self.used_images: set[str] = set()
        self.current_slug = ""

    # -- 占位符 ---------------------------------------------------------- #
    def hold(self, content: str) -> str:
        self.placeholders.append(content)
        return f"\x00{len(self.placeholders) - 1}\x00"

    def release(self, text: str) -> str:
        def sub(m: re.Match) -> str:
            return self.placeholders[int(m.group(1))]
        for _ in range(3):  # 占位符里可能还有占位符
            new = re.sub(r"\x00(\d+)\x00", sub, text)
            if new == text:
                break
            text = new
        return text

    # -- 链接 ------------------------------------------------------------ #
    def img_prefix(self) -> str:
        """图片相对当前页面的前缀（页面在 wiki/ 下，图片在 docs/assets/ 下）。"""
        depth = self.current_slug.count("/") + 1
        return "../" * depth + self.images_url_prefix

    def rel_link(self, target: str) -> str | None:
        target = target.strip()
        slug = self.slug_map.get(target)
        if slug is None:
            # 去掉消歧义后缀再试：郝瑟（ISTJ） → 郝瑟
            base = re.sub(r"[（(][^）)]*[）)]$", "", target)
            for k, v in self.slug_map.items():
                if re.sub(r"[（(][^）)]*[）)]$", "", k) == base:
                    slug = v
                    break
        if slug is None:
            self.unknown_links.add(target)
            return None
        depth = self.current_slug.count("/")
        prefix = "../" * depth if depth else ""
        # 同目录或跨目录都用相对路径
        cur_dir = os.path.dirname(self.current_slug)
        tgt = slug
        rel = os.path.relpath(tgt, cur_dir or ".").replace("\\", "/")
        return rel + ".md"

    def wiki_link(self, inner: str) -> str:
        parts = split_top_level(inner, "|")
        target = parts[0].strip()
        label = parts[-1].strip() if len(parts) > 1 else target
        label = re.sub(r"^\s*\|", "", label)

        if target.lower().startswith("category:"):
            self.tags.append(target.split(":", 1)[1].strip())
            return ""
        if target.lower().startswith(("file:", "image:")):
            return self.file_link(parts)
        href = self.rel_link(target)
        if href is None:
            return label  # 目标页不存在，保留纯文本
        return f"[{label}]({href})"

    def file_link(self, parts: list[str]) -> str:
        raw = parts[0].split(":", 1)[1].strip()
        name = re.sub(r"@.*$", "", raw.split("|")[0]).strip()  # 去掉 @128w 之类
        caption = ""
        for p in parts[1:]:
            p = p.strip()
            if p and not re.fullmatch(r"(thumb|thumbnail|frame|frameless|\d+px|left|right|center|none|baseline|sub|super|top|text-top|middle|bottom|text-bottom)", p, re.I):
                caption = p
        if name not in self.image_names:
            return f"*（图片 {name} 未找到）*" if not caption else f"*{caption}*"
        self.used_images.add(name)
        src = f"{self.img_prefix()}/{name}"
        return f"![{caption or name}]({src})" + (f"\n\n*{caption}*" if caption else "")

    # -- 模板 ------------------------------------------------------------ #
    def template(self, inner: str) -> str:
        parts = split_top_level(inner, "|")
        name = parts[0].strip()
        params = parts[1:]

        if name == "SITENAME":
            return "王维诗里的MBTI Wiki"
        if name.startswith("Special:"):
            return "*（动态内容：最近更改，静态站点无法显示）*"
        if name in INFOBOX_TEMPLATES:
            return self.infobox(params)
        low = name.lower()
        if low in {d.lower() for d in DROP_TEMPLATES} or not params:
            self.dropped_templates[name] = self.dropped_templates.get(name, 0) + 1
            return ""
        self.dropped_templates[name] = self.dropped_templates.get(name, 0) + 1
        return ""

    def infobox(self, params: list[str]) -> str:
        rows: list[tuple[str, str]] = []
        gallery_md = ""
        for p in params:
            if "=" not in p:
                continue
            key, _, val = p.partition("=")
            key, val = key.strip(), val.strip()
            label = LABELS.get(key, key)
            if label is None and key in ("title1", "title", "基本信息"):
                continue
            if not val:
                continue
            # 参数值里可能是占位符（画廊等块级内容在 protect() 阶段已被抽走）
            resolved = self.release(val) if "\x00" in val else val
            if "<gallery" in resolved.lower():
                # 信息框只放第一张立绘，完整图集在正文的「图库」小节
                gallery_md = self.gallery(resolved, limit=1)
                continue
            if key in ("image1", "image"):
                if val.startswith("http"):
                    rows.append((label or "图片", f"![]({val})"))
                else:
                    name = re.sub(r"^(file|image)\s*:\s*", "",
                                  re.sub(r"@.*$", "", val), flags=re.I)
                    if name in self.image_names:
                        self.used_images.add(name)
                        rows.append((label or "图片",
                                     f"![{name}]({self.img_prefix()}/{name})"))
                    else:
                        rows.append((label or "图片", f"*（图片 {name} 未找到）*"))
                continue
            val = self.inline(self.convert_links(val)) if "[" in val else self.inline(val)
            rows.append((label or key, val.replace("\n", " ")))

        out = []
        if gallery_md:
            out.append(gallery_md)
        if rows:
            cells = "".join(
                f"<tr><th>{H.escape(k)}</th><td>{v}</td></tr>" for k, v in rows
            )
            out.append(f'<table class="wiki-infobox">{cells}</table>')
        return "\n\n".join(out)

    def gallery(self, block: str, limit: int = 0) -> str:
        inner = re.sub(r"^<gallery[^>]*>|</gallery>$", "", block.strip(), flags=re.I | re.S)
        figs = []
        for line in inner.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            bits = [b.strip() for b in line.split("|")]
            name = re.sub(r"@.*$", "", bits[0])
            name = re.sub(r"^(file|image)\s*:\s*", "", name, flags=re.I)
            caption = bits[1] if len(bits) > 1 else ""
            if name not in self.image_names:
                figs.append(f'<figure><figcaption>{H.escape(caption or name)}'
                            f'（图片缺失）</figcaption></figure>')
                if limit and len(figs) >= limit:
                    break
                continue
            self.used_images.add(name)
            src = f"{self.img_prefix()}/{name}"
            figs.append(
                f'<figure><img src="{src}" alt="{H.escape(caption or name)}" loading="lazy">'
                f'<figcaption>{H.escape(caption or name)}</figcaption></figure>'
            )
            if limit and len(figs) >= limit:
                break
        return f'<div class="{GALLERY_CSS_CLASS}">{"".join(figs)}</div>'

    # -- 表格 ------------------------------------------------------------ #
    def table(self, block: str) -> str:
        lines = block.splitlines()
        caption = ""
        collapsible = "mw-collapsible" in lines[0]
        rows: list[list[tuple[str, str]]] = []  # (attrs, text)
        cur: list[tuple[str, str]] | None = None
        header_rows: set[int] = set()

        i = 1
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("|+") and not caption:
                caption = stripped[2:].strip()
                i += 1
                continue
            if stripped.startswith("|-"):
                if cur is not None:
                    rows.append(cur)
                cur = []
                i += 1
                continue
            if stripped.startswith("|}") or stripped == "":
                i += 1
                continue
            if stripped.startswith("!") and not stripped.startswith("!-"):
                if cur is None:
                    cur = []
                    header_rows.add(len(rows))
                for cell in split_top_level(stripped[1:], "!!"):
                    cur.append(self._cell(cell))
                i += 1
                continue
            if stripped.startswith("|"):
                if cur is None:
                    cur = []
                for cell in split_top_level(stripped[1:], "||"):
                    cur.append(self._cell(cell))
                i += 1
                continue
            # 续行
            if cur:
                attrs, text = cur[-1]
                cur[-1] = (attrs, text + "\n" + stripped)
            i += 1
        if cur:
            rows.append(cur)
        rows = [r for r in rows if r]
        # 单元格里的 [[链接]] '''粗体''' 等也要转换
        rows = [[(a, self.inline(t)) for a, t in r] for r in rows]

        if not rows:
            return ""

        merged = any(re.search(r"colspan|rowspan", a, re.I) for r in rows for a, _ in r)
        if merged:
            body = []
            for ri, r in enumerate(rows):
                tds = []
                for attrs, text in r:
                    tag = "th" if ri in header_rows else "td"
                    keep = re.findall(r'(colspan|rowspan)="\d+"', attrs, re.I) or []
                    attr_s = ""
                    for k in keep:
                        m = re.search(rf'{k}="(\d+)"', attrs, re.I)
                        if m:
                            attr_s += f' {k.lower()}="{m.group(1)}"'
                    tds.append(f"<{tag}{attr_s}>{text}</{tag}>")
                body.append("<tr>" + "".join(tds) + "</tr>")
            tbl = f'<table class="wiki-table">{"".join(body)}</table>'
        else:
            width = max(len(r) for r in rows)
            out_lines = []
            header = rows[0]
            out_lines.append("| " + " | ".join(t.replace("|", "\\|") or " " for _, t in header) +
                             " |" + (" x" * (width - len(header)) if width > len(header) else ""))
            out_lines.append("|" + "---|" * width)
            for r in rows[1:]:
                cells = [t.replace("|", "\\|").replace("\n", " ") or " " for _, t in r]
                cells += [" "] * (width - len(cells))
                out_lines.append("| " + " | ".join(cells) + " |")
            tbl = "\n".join(out_lines)

        if caption and not merged:
            cap = self.inline(caption).strip()
            if "**" not in cap:
                cap = f"**{cap}**"
            tbl = f"\n\n{cap}\n\n{tbl}\n\n"
        elif caption:
            cap = self.inline(caption).strip()
            tbl = (f'\n\n<div class="wiki-table-caption">{cap}</div>\n\n{tbl}\n\n')
        if collapsible:
            title = strip_html(self.inline(caption)).replace("'''", "").replace("**", "").strip() \
                or "展开查看"
            tbl = f'\n\n??? note "{title}"\n\n    ' + tbl.strip().replace("\n", "\n    ") + "\n\n"
        return tbl

    @staticmethod
    def _cell(cell: str) -> tuple[str, str]:
        cell = cell.strip()
        m = re.match(r'^([^|]*\|)?\s*(.*)$', cell, re.S)
        attrs = ""
        if "|" in cell:
            head, _, rest = cell.partition("|")
            if re.search(r'(colspan|rowspan|align|style|class|width|bgcolor)\s*=', head, re.I):
                attrs, cell = head, rest
        return attrs, cell.strip().strip("|").strip()

    # -- 文本级 ---------------------------------------------------------- #
    def convert_links(self, text: str) -> str:
        # [[...]]
        out = []
        i = 0
        while True:
            s = text.find("[[", i)
            if s < 0:
                out.append(text[i:])
                break
            e = text.find("]]", s)
            if e < 0:
                out.append(text[i:])
                break
            # 嵌套保护
            inner = text[s + 2:e]
            while inner.count("[[") > inner.count("]]") and e >= 0:
                nxt = text.find("]]", e + 2)
                if nxt < 0:
                    break
                e = nxt
                inner = text[s + 2:e]
            out.append(text[i:s])
            out.append(self.wiki_link(inner))
            i = e + 2
        return "".join(out)

    def inline(self, text: str) -> str:
        # MediaWiki 的转义模板
        text = text.replace("{{!}}", "|").replace("{{=}}", "=")
        text = self.convert_links(text)
        # 外链 [url 文字] / [url]
        def ext(m: re.Match) -> str:
            url, label = m.group(1), m.group(2)
            if label is None:
                return f"<{url}>"
            return f"[{label.strip()}]({url})"
        text = re.sub(r"\[(https?://[^\s\]]+)(?:\s+([^\]]+))?\]", ext, text)
        # 语言变体 -{zh-hans:简体; zh-hant:繁體;}-
        text = re.sub(r"-\{[^{}]*?zh-hans:([^;{}]*)[^{}]*\}-", r"\1", text)
        text = re.sub(r"-\{[^{}]*?zh-cn:([^;{}]*)[^{}]*\}-", r"\1", text)
        text = re.sub(r"-\{[^{}]*\}-", "", text)
        # 粗斜体
        text = re.sub(r"'''''(.*?)'''''", r"***\1***", text, flags=re.S)
        text = re.sub(r"'''(.*?)'''", r"**\1**", text, flags=re.S)
        text = re.sub(r"''(.*?)''", r"*\1*", text, flags=re.S)
        return text

    # -- 主流程 ---------------------------------------------------------- #
    def protect(self, text: str) -> str:
        # nowiki：内容原样保留（其中的 | 不能当分隔符）
        for s, e in reversed(find_blocks(text, "<nowiki>", "</nowiki>")):
            inner = text[s + 8:e - 9]
            text = text[:s] + self.hold(inner) + text[e:]
        text = re.sub(r"<nowiki\s*/>", "", text)
        # ref：丢弃
        text = re.sub(r"<ref[^>]*/>", "", text)
        for s, e in reversed(find_blocks(text, "<ref", "</ref>")):
            text = text[:s] + text[e:]
        # 模板要在画廊/表格之前抽走，这样 {{信息框|image1=<gallery>..}} 能拿到原始画廊
        for s, e in reversed(find_blocks(text, "{{", "}}")):
            text = text[:s] + self.hold(self.template(text[s + 2:e - 2])) + text[e:]
        # 表格
        for s, e in reversed(find_blocks(text, "{|", "|}")):
            text = text[:s] + self.hold(self.table(text[s:e])) + text[e:]
        # 画廊
        for s, e in reversed(find_blocks(text, "<gallery", "</gallery>")):
            text = text[:s] + self.hold(self.gallery(text[s:e])) + text[e:]
        return text

    def convert(self, text: str, title: str, slug: str) -> str:
        self.current_slug = slug
        self.tags = []
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # #REDIRECT [[目标]] —— 重定向页
        m = re.match(r"^\s*#(?:REDIRECT|重定向)\s*:?\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
                     text, re.I)
        if m:
            target, label = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
            href = self.rel_link(target)
            body = (f"本页原为重定向页，指向 [{label}]({href})。" if href
                    else f"本页原为重定向页，指向 {label}（目标页未迁移）。")
            return (f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\n---\n\n"
                    + f"# {title}\n\n" + body + "\n")

        text = self.protect(text)

        lines = text.split("\n")
        out: list[str] = [f"# {title}", ""]
        for line in lines:
            s = line.rstrip()
            # 首页用的栏目标记
            if re.match(r"^\s*<mainpage-.*?/?>\s*$", s, re.I):
                continue
            if re.match(r"^\s*__(NOTOC|NOEDITSECTION|TOC)__\s*$", s):
                continue
            # 标题：== X == → ## X （一级标题让给页面标题）
            m = re.match(r"^(={1,6})\s*(.+?)\s*\1\s*$", s)
            if m:
                level = max(2, min(len(m.group(1)), 6))
                heading = self.inline(m.group(2))
                out.append("")
                out.append("#" * level + " " + heading)
                out.append("")
                continue
            # 水平线
            if re.match(r"^-{4,}\s*$", s):
                out.append("")
                out.append("---")
                out.append("")
                continue
            # 列表
            m = re.match(r"^([*#]+)\s*(.*)$", s)
            if m:
                marks, body = m.group(1), self.inline(m.group(2))
                indent = "    " * (len(marks) - 1)
                bullet = "-" if marks[-1] == "*" else "1."
                out.append(f"{indent}{bullet} {body}")
                continue
            # 定义列表
            m = re.match(r"^([;:])\s*(.*)$", s)
            if m:
                out.append(self.inline(m.group(2)))
                continue
            out.append(self.inline(s))

        body = "\n".join(out)
        body = re.sub(r"\n{3,}", "\n\n", body)
        body = self.release(body)
        body = self.release(body)
        # 块级 HTML 后面要空行，否则紧跟的文字会被吞进同一行
        body = re.sub(r"</table>(?=[^\s\n])", "</table>\n\n", body)
        body = re.sub(r"</div>(?=[^\s<\n])", "</div>\n\n", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        tags = []
        for t in self.tags:
            t = strip_html(t).strip()
            if t and t not in tags:
                tags.append(t)
        front = ["---", f"title: {json.dumps(title, ensure_ascii=False)}"]
        if tags:
            front.append("tags:")
            front += [f"  - {json.dumps(t, ensure_ascii=False)}" for t in tags]
        front.append("---")
        return "\n".join(front) + "\n\n" + body + "\n"


# --------------------------------------------------------------------------- #
# 读取导出文件
# --------------------------------------------------------------------------- #
def read_pages(xml_path: str) -> tuple[dict, list[dict]]:
    root = ET.parse(xml_path).getroot()
    siteinfo = {}
    si = root.find(MW_NS + "siteinfo")
    if si is not None:
        for child in si:
            key = child.tag.split("}")[-1]
            if key != "namespaces":
                siteinfo[key] = child.text
    pages = []
    for p in root.findall(MW_NS + "page"):
        title = p.findtext(MW_NS + "title") or ""
        ns = p.findtext(MW_NS + "ns") or "0"
        rev = p.find(MW_NS + "revision")
        text = ""
        if rev is not None:
            t = rev.find(MW_NS + "text")
            if t is not None and t.text:
                text = t.text
        pages.append({"title": title, "ns": ns, "text": text})
    return siteinfo, pages


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", required=True)
    ap.add_argument("--docs", required=True, help="输出到 docs/wiki 目录")
    ap.add_argument("--images", default=None, help="图片源目录（archive 的 images/）")
    ap.add_argument("--images-url", default="assets/wiki-images",
                    help="站点内图片相对路径（相对 docs 根）")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    siteinfo, pages = read_pages(args.xml)
    content = [p for p in pages if p["ns"] == "0"]

    # 图片清单：优先用 archive 里真实存在的文件，其次用导出里的 File: 页
    images: set[str] = set()
    if args.images and os.path.isdir(args.images):
        images = {os.path.basename(f) for f in glob.glob(os.path.join(args.images, "*"))}
    for p in pages:
        if p["ns"] == "6":
            images.add(p["title"].split(":", 1)[1])

    slug_map = {}
    for p in content:
        slug_map[p["title"]] = PAGE_SLUGS.get(p["title"], "misc/" + slugify_fallback(p["title"]))

    conv = Converter(slug_map, images, args.images_url)
    os.makedirs(args.docs, exist_ok=True)

    written = []
    for p in content:
        slug = slug_map[p["title"]]
        md = conv.convert(p["text"], p["title"], slug)
        dest = os.path.join(args.docs, slug + ".md")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(md)
        written.append({"title": p["title"], "slug": slug, "bytes": len(md),
                        "tags": list(conv.tags)})

    # 图片复制
    copied = missing = 0
    if args.images and os.path.isdir(args.images):
        dst_dir = os.path.join(os.path.dirname(args.docs.rstrip("/\\")), args.images_url)
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(conv.used_images):
            src = os.path.join(args.images, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dst_dir, name))
                copied += 1
            else:
                missing += 1

    print(f"转换完成：{len(written)} 个页面 → {args.docs}")
    print(f"  图片：引用 {len(conv.used_images)}，复制 {copied}，缺失 {missing}")
    if conv.unknown_links:
        print(f"  未解析的内部链接 {len(conv.unknown_links)} 个：{sorted(conv.unknown_links)[:8]}")
    if conv.dropped_templates:
        top = sorted(conv.dropped_templates.items(), key=lambda kv: -kv[1])[:6]
        print(f"  丢弃的模板：{top}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write("# 转换报告\n\n")
            fh.write(f"- 源文件：`{os.path.basename(args.xml)}`\n")
            fh.write(f"- 站点名：{siteinfo.get('sitename')}\n")
            fh.write(f"- 正文页：{len(written)}\n")
            fh.write(f"- 引用图片：{len(conv.used_images)}（复制 {copied}，缺失 {missing}）\n\n")
            fh.write("## 页面\n\n| 标题 | 输出 | 字节 | 标签 |\n|---|---|---|---|\n")
            for w in written:
                fh.write(f"| {w['title']} | `{w['slug']}.md` | {w['bytes']} | "
                         f"{'、'.join(w['tags'])} |\n")
            fh.write("\n## 未解析的内部链接\n\n")
            fh.write("\n".join(f"- {t}" for t in sorted(conv.unknown_links)) or "（无）")
            fh.write("\n\n## 丢弃的模板\n\n")
            fh.write("\n".join(f"- `{k}` × {v}" for k, v in
                               sorted(conv.dropped_templates.items(), key=lambda kv: -kv[1]))
                     or "（无）")
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
