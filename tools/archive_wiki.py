#!/usr/bin/env python3
"""
archive_wiki.py — 把一个 Fandom / MediaWiki 站点完整抓取到本地。

保存内容：
  pages/<命名空间>/<标题>.html   —— 渲染后的正文 HTML（离线可读，带统一样式）
  wikitext/<命名空间>/<标题>.wiki —— 原始 wikitext（用于之后转 Markdown）
  images/<文件名>                 —— 所有图片原图
  meta/siteinfo.json              —— 站点信息
  meta/pages.json                 —— 全部页面清单
  meta/images.json                —— 图片清单（文件名 / URL / 大小 / sha1）
  index.html                      —— 离线索引页（页面 + 图片画廊）

特性：断点续传（已存在的文件会跳过）、自动重试、分页、限速。

用法（需要你的加速器开着）：
    python archive_wiki.py --base https://wangweishilidembti.fandom.com --out fandom-archive

如果加速器是本地 HTTP 代理（常见端口 7890 / 10809 / 1080）：
    python archive_wiki.py --base https://wangweishilidembti.fandom.com --out fandom-archive --proxy http://127.0.0.1:7890

如果 Cloudflare 拦住了（提示 Just a moment...），从浏览器复制 cf_clearance 等 Cookie：
    python archive_wiki.py --base ... --out ... --cookie "cf_clearance=xxx; ..."
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CSS = """
:root { color-scheme: light dark; }
body { max-width: 52rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.75;
       font-family: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; margin: 1rem 0; display: block; overflow-x: auto; }
th, td { border: 1px solid #8884; padding: .35rem .6rem; text-align: left; }
th { background: #8882; }
a { color: #0b6bcb; }
.nav { font-size: .9rem; opacity: .8; margin-bottom: 1.5rem; }
.nav a { margin-right: .8rem; }
h1 { font-size: 1.6rem; border-bottom: 1px solid #8884; padding-bottom: .4rem; }
blockquote { border-left: 3px solid #8886; margin-left: 0; padding-left: 1rem; opacity: .9; }
.gallery { display: flex; flex-wrap: wrap; gap: .75rem; }
.gallery figure { margin: 0; width: 11rem; }
.gallery img { width: 100%; height: 9rem; object-fit: contain; background: #8881; }
.gallery figcaption { font-size: .75rem; word-break: break-all; opacity: .85; }
"""


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Fetcher:
    def __init__(self, proxy: str | None, cookie: str | None, delay: float):
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        else:
            handlers.append(urllib.request.ProxyHandler({}))  # ignore broken system proxy
        self.opener = urllib.request.build_opener(*handlers)
        self.cookie = cookie
        self.delay = delay
        self.last = 0.0
        self.count = 0

    def _throttle(self):
        gap = time.time() - self.last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self.last = time.time()

    def raw(self, url: str, tries: int = 4, timeout: int = 60) -> bytes:
        # 中文文件名等非 ASCII 字符必须百分号编码，否则 urllib 会报 ascii codec 错误
        url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        last_err: Exception | None = None
        for attempt in range(1, tries + 1):
            self._throttle()
            self.count += 1
            try:
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (403, 429, 503) and attempt < tries:
                    time.sleep(3 * attempt)
                    continue
                raise
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < tries:
                    time.sleep(2 * attempt)
        raise RuntimeError(f"请求失败 {url}: {last_err}")

    def json(self, url: str, **kw) -> dict:
        body = self.raw(url, **kw)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            head = body[:300].decode("utf-8", "replace")
            raise RuntimeError(
                "返回的不是 JSON（多半被 Cloudflare 拦截了）。请用 --cookie 传入浏览器 Cookie。\n"
                f"响应开头：{head!r}"
            )


def api_url(base: str, params: dict) -> str:
    return f"{base}/api.php?" + urllib.parse.urlencode(params)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
NS_DIR = {
    "0": "main", "1": "talk", "2": "user", "3": "user-talk", "4": "project",
    "5": "project-talk", "6": "file", "7": "file-talk", "8": "mediawiki",
    "9": "mediawiki-talk", "10": "template", "11": "template-talk",
    "12": "help", "13": "help-talk", "14": "category", "15": "category-talk",
    "828": "module", "829": "module-talk",
    "110": "forum", "502": "user-blog", "1200": "message-wall", "2000": "board",
}


def safe_name(title: str, ns: str) -> str:
    name = title.split(":", 1)[1] if ":" in title and ns != "0" else title
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return (name or "untitled")[:150]


def detect_api_base(f: Fetcher, base: str, prefix: str | None) -> str:
    candidates = []
    if prefix:
        candidates.append(base.rstrip("/") + prefix)
    candidates += [base.rstrip("/"), base.rstrip("/") + "/zh"]
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            data = f.json(api_url(cand, {"action": "query", "meta": "siteinfo",
                                         "siprop": "general", "format": "json"}), tries=2)
            if "query" in data:
                print(f"[api] 使用接口地址: {cand}/api.php")
                return cand
        except Exception as e:  # noqa: BLE001
            print(f"[api] {cand}/api.php 不可用 ({str(e)[:80]})")
    raise SystemExit("找不到可用的 api.php —— 请确认加速器已开启，或提供 --cookie。")


def write(path: str, data: bytes | str) -> bool:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(path, mode, **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as fh:
        fh.write(data)
    return True


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(description="抓取整个 MediaWiki/Fandom 站点")
    ap.add_argument("--base", required=True, help="站点根地址，如 https://xxx.fandom.com")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--prefix", default=None, help="语言路径前缀，如 /zh（默认自动探测）")
    ap.add_argument("--ns", default="all", help="要抓的命名空间，逗号分隔；all=全部；默认 all")
    ap.add_argument("--proxy", default=None, help="HTTP 代理，如 http://127.0.0.1:7890")
    ap.add_argument("--cookie", default=None, help="Cookie 字符串（Cloudflare 拦截时需要）")
    ap.add_argument("--delay", type=float, default=0.4, help="请求间隔秒数（默认 0.4）")
    ap.add_argument("--no-images", action="store_true", help="不下载图片")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 个页面（调试用）")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    f = Fetcher(args.proxy, args.cookie, args.delay)
    api = detect_api_base(f, args.base, args.prefix)

    # ---- siteinfo -------------------------------------------------------- #
    si = f.json(api_url(api, {"action": "query", "meta": "siteinfo",
                              "siprop": "general|namespaces|statistics", "format": "json"}))
    general = si["query"]["general"]
    namespaces = si["query"]["namespaces"]
    write(os.path.join(out, "meta", "siteinfo.json"),
          json.dumps(si, ensure_ascii=False, indent=2))
    print(f"[site] {general.get('sitename')}  (dbname={general.get('dbname')}, "
          f"generator={general.get('generator')})")

    if args.ns == "all":
        want_ns = sorted((str(k) for k in namespaces if int(k) >= 0), key=int)
    else:
        want_ns = [s.strip() for s in args.ns.split(",") if s.strip()]

    # ---- enumerate pages ------------------------------------------------- #
    pages: list[dict] = []
    for ns in want_ns:
        cont: dict = {}
        while True:
            params = {"action": "query", "list": "allpages", "apnamespace": ns,
                      "aplimit": "500", "format": "json", **cont}
            data = f.json(api_url(api, params))
            got = data.get("query", {}).get("allpages", [])
            for p in got:
                pages.append({"pageid": p["pageid"], "ns": p["ns"], "title": p["title"]})
            if "continue" in data:
                cont = data["continue"]
            else:
                break
        if pages and args.limit:
            if len(pages) >= args.limit:
                pages = pages[: args.limit]
                break
    write(os.path.join(out, "meta", "pages.json"),
          json.dumps(pages, ensure_ascii=False, indent=2))
    print(f"[page] 共 {len(pages)} 个页面待抓取")

    # ---- per-page: rendered HTML + wikitext ------------------------------ #
    done_path = os.path.join(out, "meta", "done.json")
    done: set[str] = set()
    if os.path.exists(done_path):
        try:
            done = set(json.load(open(done_path, encoding="utf-8")))
        except Exception:  # noqa: BLE001
            done = set()

    made_html = made_wiki = 0
    for i, p in enumerate(pages, 1):
        if p["title"] in done:
            continue
        ns_dir = NS_DIR.get(str(p["ns"]), f"ns{p['ns']}")
        stem = safe_name(p["title"], str(p["ns"]))
        html_path = os.path.join(out, "pages", ns_dir, stem + ".html")
        wiki_path = os.path.join(out, "wikitext", ns_dir, stem + ".wiki")

        if not (os.path.exists(html_path) and os.path.getsize(html_path) > 0):
            try:
                d = f.json(api_url(api, {"action": "parse", "page": p["title"],
                                         "prop": "text|displaytitle", "redirects": "1",
                                         "format": "json", "formatversion": "2"}))
                body = d.get("parse", {}).get("text", "")
                title = re.sub(r"<[^>]+>", "", d.get("parse", {}).get("displaytitle", p["title"]))
                doc = (
                    "<!doctype html>\n<html lang=\"zh\">\n<head>\n<meta charset=\"utf-8\">\n"
                    f"<title>{html.escape(title)}</title>\n"
                    "<link rel=\"stylesheet\" href=\"../../assets/archive.css\">\n"
                    "</head>\n<body>\n"
                    f"<div class=\"nav\"><a href=\"../../index.html\">← 索引</a>"
                    f"<span>命名空间 {p['ns']}</span></div>\n"
                    f"<h1>{html.escape(title)}</h1>\n{body}\n</body>\n</html>\n"
                )
                made_html += write(html_path, doc)
            except Exception as e:  # noqa: BLE001
                print(f"  ! HTML 失败: {p['title']} — {str(e)[:100]}", flush=True)

        if not (os.path.exists(wiki_path) and os.path.getsize(wiki_path) > 0):
            try:
                d = f.json(api_url(api, {"action": "query", "prop": "revisions",
                                         "rvprop": "content", "rvslots": "main",
                                         "titles": p["title"], "format": "json",
                                         "formatversion": "2"}))
                pg = d.get("query", {}).get("pages", [{}])[0]
                content = (pg.get("revisions", [{}])[0]
                             .get("slots", {}).get("main", {}).get("content", ""))
                # 空页面也写出（0 字节），并用 done.json 记录，避免每次重抓
                write(wiki_path, content or "")
                made_wiki += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! wikitext 失败: {p['title']} — {str(e)[:100]}", flush=True)

        done.add(p["title"])
        if i % 20 == 0:
            write(done_path, json.dumps(sorted(done), ensure_ascii=False, indent=2))

        if i % 20 == 0 or i == len(pages):
            print(f"  … {i}/{len(pages)}  新增 html={made_html} wiki={made_wiki} "
                  f"请求数={f.count}", flush=True)
    write(done_path, json.dumps(sorted(done), ensure_ascii=False, indent=2))

    # ---- images ---------------------------------------------------------- #
    images: list[dict] = []
    if not args.no_images:
        cont = {}
        while True:
            params = {"action": "query", "generator": "allimages", "gailimit": "50",
                      "prop": "imageinfo", "iiprop": "url|size|mime|sha1",
                      "format": "json", "formatversion": "2", **cont}
            data = f.json(api_url(api, params))
            for img in data.get("query", {}).get("pages", []):
                info = (img.get("imageinfo") or [{}])[0]
                if info.get("url"):
                    images.append({"name": img.get("title", "").removeprefix("File:"),
                                   "url": info["url"], "size": info.get("size"),
                                   "mime": info.get("mime"), "sha1": info.get("sha1")})
            if "continue" in data:
                cont = data["continue"]
            else:
                break

        write(os.path.join(out, "meta", "images.json"),
              json.dumps(images, ensure_ascii=False, indent=2))
        print(f"[img ] 共 {len(images)} 个图片待下载")
        ok = skipped = failed = 0
        for n, img in enumerate(images, 1):
            dest = os.path.join(out, "images", img["name"])
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                skipped += 1
                continue
            try:
                blob = f.raw(img["url"], timeout=120)
                write(dest, blob)
                ok += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  ! 图片失败: {img['name']} — {str(e)[:90]}")
            if n % 15 == 0 or n == len(images):
                print(f"  … {n}/{len(images)}  下载={ok} 跳过={skipped} 失败={failed}")

    # ---- assets + index -------------------------------------------------- #
    write(os.path.join(out, "assets", "archive.css"), CSS)

    rows = []
    for p in pages:
        ns_dir = NS_DIR.get(str(p["ns"]), f"ns{p['ns']}")
        stem = safe_name(p["title"], str(p["ns"]))
        rows.append(
            f"<tr><td>{p['ns']}</td>"
            f"<td><a href=\"pages/{ns_dir}/{urllib.parse.quote(stem)}.html\">{html.escape(p['title'])}</a></td>"
            f"<td><a href=\"wikitext/{ns_dir}/{urllib.parse.quote(stem)}.wiki\">wiki</a></td></tr>"
        )
    gallery = "".join(
        f"<figure><img src=\"images/{urllib.parse.quote(i['name'])}\" loading=\"lazy\">"
        f"<figcaption>{html.escape(i['name'])}</figcaption></figure>"
        for i in images
    )
    write(os.path.join(out, "index.html"), f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>{html.escape(general.get('sitename', 'archive'))} — 离线存档</title>
<link rel="stylesheet" href="assets/archive.css"></head><body>
<h1>{html.escape(general.get('sitename', 'archive'))}</h1>
<p>来源：<a href="{html.escape(args.base)}">{html.escape(args.base)}</a>　
抓取时间：{time.strftime('%Y-%m-%d %H:%M:%S')}　
页面 {len(pages)}　图片 {len(images)}</p>
<h2>页面</h2>
<table><tr><th>ns</th><th>标题</th><th>源文</th></tr>{''.join(rows)}</table>
<h2>图片（{len(images)}）</h2>
<div class="gallery">{gallery}</div>
</body></html>
""")

    print(f"\n完成 → {out}")
    print(f"  页面 {len(pages)}（HTML {made_html} 新写入）、图片 {len(images)}")
    print(f"  离线索引：{os.path.join(out, 'index.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
