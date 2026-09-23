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

# 角色页标题里就写着人格类型，可以据此补全源文件缺失的分类标签
LETTER_TAGS = {"I": "I人", "E": "E人", "N": "N人", "S": "S人",
               "T": "T人", "F": "F人", "J": "J人", "P": "P人"}


def infer_tags(title: str) -> list[str]:
    """从「某某（INTJ）」这样的标题推出 I人/N人/T人/J人 + 四色分组标签。

    四色分组的判定：第 2 位是 N → 分析家(NT)/外交家(NF)；
    第 2 位是 S → 第 4 位是 J 则守护者(SJ)，否则探险家(SP)。
    """
    m = re.search(r"[（(]([IE][NS][TF][JP])[）)]", title)
    if not m:
        return []
    t = m.group(1)
    tags = [LETTER_TAGS[c] for c in t]
    if t[1] == "N":
        group = "紫人组" if t[2] == "T" else "绿人组"
    else:
        group = "蓝人组" if t[3] == "J" else "黄人组"
    tags.append(group)
    return tags


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
    def __init__(self, slug_map: dict[str, str], image_names: set[str],
                 images_url_prefix: str, disk_images: set[str] | None = None):
        self.slug_map = slug_map
        self.image_names = image_names
        self.disk_images = disk_images or set()
        # wikitext 里写的是 xxx.png，但抓到的可能是 Fandom 的 xxx.webp 缩略图，
        # 这里按「主文件名」建索引；磁盘上真实存在的文件名优先。
        self.image_index: dict[str, str] = {}
        for n in sorted(self.disk_images):
            self.image_index.setdefault(os.path.splitext(n)[0].lower(), n)
        for n in sorted(image_names):
            self.image_index.setdefault(os.path.splitext(n)[0].lower(), n)
        self.images_url_prefix = images_url_prefix
        self.placeholders: list[str] = []
        self.tags: list[str] = []
        self.dropped_templates: dict[str, int] = {}
        self.unknown_links: set[str] = set()
        self.used_images: set[str] = set()
        self.missing_images: set[str] = set()
        self.current_slug = ""
        self.current_title = ""

    def resolve_image(self, name: str) -> str | None:
        """把 wikitext 里的图片名解析成磁盘上真实存在的文件名。

        给了 --images（即已知磁盘上有哪些图）时，只认磁盘上真实存在的文件，
        避免为一张其实没抓到的图生成死链；没给时才退回用导出里的名称。
        """
        if not name:
            return None
        cands = (name, name.replace("_", " "), name.replace(" ", "_"))
        for cand in cands:
            if cand in self.disk_images:
                return cand
        for cand in cands:
            actual = self.image_index.get(os.path.splitext(cand)[0].lower())
            if actual and (not self.disk_images or actual in self.disk_images):
                return actual
        return None

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
        """图片相对当前页面的前缀。

        页面文件是 docs/wiki/characters/xxx.md，而 MkDocs 默认 use_directory_urls，
        实际 URL 是 /wiki/characters/xxx/ —— 比文件路径多一层目录，
        所以上跳层数 = slug 里的斜杠数 + 2（多出的那层是 use_directory_urls 造成的）。
        """
        depth = self.current_slug.count("/") + 2
        return "../" * depth + self.images_url_prefix

    @staticmethod
    def md_to_html(s: str) -> str:
        """把 Markdown 的图片/链接转成真正的 HTML 标签。

        信息框是裸 HTML 表格，Python-Markdown 不会处理 HTML 块内部的 Markdown，
        所以 ![]() 和 []() 必须自己转成 <img> / <a>，否则会原样显示出来。
        """
        s = re.sub(
            r"!\[([^\]]*)\]\(([^)\s]+)\)",
            lambda m: f'<img src="{m.group(2)}" alt="{H.escape(m.group(1))}" loading="lazy">',
            s,
        )
        s = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
            s,
        )
        s = re.sub(
            r"&lt;(https?://[^&\s]+)&gt;",
            lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>',
            s,
        )
        return s

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
        actual = self.resolve_image(name)
        if actual is None:
            self.missing_images.add(name)
            # 图片确实抓不到时给一句轻量提示，不暴露原始文件名
            return f"*（图片暂缺）*" if not caption else f"*{caption}*"
        self.used_images.add(actual)
        src = f"{self.img_prefix()}/{actual}"
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
        """生成信息卡。

        整体是一张裸 HTML 表格：第一行跨两列放立绘，后面是「标签 / 取值」行。
        因为 Markdown 不会在 HTML 块内部生效，取值里的图片和链接要转成真标签，
        否则页面上会直接显示出 ![..](..) 这样的源码。
        """
        rows: list[tuple[str, str]] = []
        portrait = ""
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
                # 信息卡只放第一张立绘，完整图集在正文的「图库」小节
                portrait = portrait or self.gallery_first_img(resolved)
                continue
            if key in ("image1", "image"):
                if val.startswith("http"):
                    portrait = portrait or f'<img src="{val}" alt="{H.escape(label or "图片")}">'
                else:
                    name = re.sub(r"^(file|image)\s*:\s*", "",
                                  re.sub(r"@.*$", "", val), flags=re.I)
                    actual = self.resolve_image(name)
                    if actual:
                        self.used_images.add(actual)
                        portrait = portrait or (
                            f'<img src="{self.img_prefix()}/{actual}" '
                            f'alt="{H.escape(name)}" loading="lazy">'
                        )
                continue
            # {{!}} 是 MediaWiki 的转义竖线，信息卡里当作换行更耐看
            val = val.replace("{{!}}", "<br>")
            val = self.inline(val)
            val = self.md_to_html(val)
            rows.append((label or key, val.replace("\n", " ")))

        cells = ""
        if portrait:
            cells += f'<tr><td class="wiki-infobox-figure" colspan="2">{portrait}</td></tr>'
        cells += "".join(f"<tr><th>{H.escape(k)}</th><td>{v}</td></tr>" for k, v in rows)
        if not cells:
            return ""
        # 用 colgroup 固定两列宽度：table-layout:fixed 下，跨列的立绘行会干扰
        # 浏览器对列宽的推断，显式声明列宽才稳。
        cols = '<colgroup><col class="wiki-col-label"><col class="wiki-col-value"></colgroup>'
        return f'<table class="wiki-infobox">{cols}{cells}</table>'

    def gallery_first_img(self, block: str) -> str:
        """取出图集里的第一张图，返回 <img> 标签（找不到就返回空串）。"""
        inner = re.sub(r"^<gallery[^>]*>|</gallery>$", "", block.strip(), flags=re.I | re.S)
        for line in inner.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            bits = [b.strip() for b in line.split("|")]
            name = re.sub(r"@.*$", "", bits[0])
            name = re.sub(r"^(file|image)\s*:\s*", "", name, flags=re.I)
            caption = bits[1] if len(bits) > 1 else name
            actual = self.resolve_image(name)
            if actual:
                self.used_images.add(actual)
                return (f'<img src="{self.img_prefix()}/{actual}" '
                        f'alt="{H.escape(caption)}" loading="lazy">')
        return ""

    def gallery(self, block: str, limit: int = 0) -> str:
        inner = re.sub(r"^<gallery[^>]*>|</gallery>$", "", block.strip(), flags=re.I | re.S)
        figs = []
        missing_here = 0
        for line in inner.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            bits = [b.strip() for b in line.split("|")]
            name = re.sub(r"@.*$", "", bits[0])
            name = re.sub(r"^(file|image)\s*:\s*", "", name, flags=re.I)
            caption = bits[1] if len(bits) > 1 else ""
            actual = self.resolve_image(name)
            if actual is None:
                missing_here += 1
                self.missing_images.add(name)
                continue
            self.used_images.add(actual)
            src = f"{self.img_prefix()}/{actual}"
            figs.append(
                f'<figure><img src="{src}" alt="{H.escape(caption or name)}" loading="lazy">'
                f'<figcaption>{H.escape(caption or name)}</figcaption></figure>'
            )
            if limit and len(figs) >= limit:
                break
        # 整组图都没有时，不要留一排空图框，给一句提示就好
        if not figs:
            return f"*（本图集的 {missing_here} 张图片暂缺）*" if missing_here else ""
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

        if caption and strip_html(caption).strip() == self.current_title.strip():
            caption = ""   # 表标题和页面标题重复，去掉更清爽

        # 表格前后必须留空行，否则会被当成上一段文字的一部分，Markdown 就不认这个表了
        tbl = tbl.strip("\n")

        # 列特别多的表格在窄屏上必然要横向滚动，给一句提示
        if not merged and width > 10:
            tbl = f'<div class="wiki-table-hint">表格较宽，可左右滑动查看</div>\n\n{tbl}'

        if caption and not merged:
            cap = self.inline(caption).strip()
            if "**" not in cap:
                cap = f"**{cap}**"
            tbl = f"{cap}\n\n{tbl}"
        elif caption:
            cap = self.inline(caption).strip()
            tbl = f'<div class="wiki-table-caption">{cap}</div>\n\n{tbl}'
        if collapsible:
            title = strip_html(self.inline(caption)).replace("'''", "").replace("**", "").strip() \
                or "展开查看"
            tbl = f'??? note "{title}"\n\n    ' + tbl.replace("\n", "\n    ")
        return f"\n\n{tbl}\n\n"

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

    def convert(self, text: str, title: str, slug: str,
                extra_tags: list[str] | None = None) -> str:
        self.current_slug = slug
        self.current_title = title
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
        for t in list(self.tags) + list(extra_tags or []):
            t = strip_html(t).strip()
            if t and t not in tags:
                tags.append(t)
        self.tags = tags
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
    ap.add_argument("--no-infer-tags", action="store_true",
                    help="不根据标题里的人格类型补全标签")
    args = ap.parse_args()

    siteinfo, pages = read_pages(args.xml)
    content = [p for p in pages if p["ns"] == "0"]

    # 图片清单：磁盘上真实存在的文件名优先，导出里的 File: 页用于补齐名称
    disk_images: set[str] = set()
    if args.images and os.path.isdir(args.images):
        disk_images = {os.path.basename(f) for f in glob.glob(os.path.join(args.images, "*"))
                       if os.path.splitext(f)[1].lower() in
                       {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"}}
    images: set[str] = set(disk_images)
    for p in pages:
        if p["ns"] == "6":
            images.add(p["title"].split(":", 1)[1])

    slug_map = {}
    for p in content:
        slug_map[p["title"]] = PAGE_SLUGS.get(p["title"], "misc/" + slugify_fallback(p["title"]))

    conv = Converter(slug_map, images, args.images_url, disk_images=disk_images)
    os.makedirs(args.docs, exist_ok=True)

    written = []
    inferred_count = 0
    for p in content:
        slug = slug_map[p["title"]]
        extra: list[str] = []
        if not args.no_infer_tags:
            source = set(re.findall(r"\[\[\s*Category\s*:\s*([^\]|]+)", p["text"], re.I))
            source = {s.strip() for s in source}
            extra = [t for t in infer_tags(p["title"]) if t not in source]
            if extra:
                inferred_count += 1
        md = conv.convert(p["text"], p["title"], slug, extra_tags=extra)
        dest = os.path.join(args.docs, slug + ".md")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(md)
        written.append({"title": p["title"], "slug": slug, "bytes": len(md),
                        "tags": list(conv.tags), "inferred": extra})

    # 图片复制
    copied = missing = 0
    if args.images and os.path.isdir(args.images):
        dst_dir = os.path.join(os.path.dirname(args.docs.rstrip("/\\")), args.images_url)
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(conv.used_images):
            src = os.path.join(args.images, name)
            dst = os.path.join(dst_dir, name)
            if not os.path.exists(src):
                missing += 1
                continue
            # 源目录和目标目录可能就是同一个（图片已经收拢好了），跳过自身拷贝
            if os.path.exists(dst) and os.path.samefile(src, dst):
                continue
            shutil.copy2(src, dst)
            copied += 1

    print(f"转换完成：{len(written)} 个页面 → {args.docs}")
    print(f"  图片：引用 {len(conv.used_images)}，复制 {copied}，缺失 {missing}")
    if conv.missing_images:
        print(f"  未抓到的图片 {len(conv.missing_images)} 张（页面里以「图片暂缺」占位）："
              f"{sorted(conv.missing_images)}")
    if inferred_count:
        print(f"  标签补全：{inferred_count} 个页面（源文件里没有分类，按标题的人格类型推出）")
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
            fh.write(f"- 引用图片：{len(conv.used_images)}（复制 {copied}，缺失 {missing}）\n")
            if inferred_count:
                fh.write(f"- 标签补全：{inferred_count} 个页面（源文件没有分类，"
                         f"按标题中的人格类型推出，标 *）\n")
            fh.write("\n## 页面\n\n| 标题 | 输出 | 字节 | 标签 |\n|---|---|---|---|\n")
            for w in written:
                tags = "、".join(
                    t + ("*" if t in w.get("inferred", []) else "") for t in w["tags"]
                )
                fh.write(f"| {w['title']} | `{w['slug']}.md` | {w['bytes']} | {tags} |\n")
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
