#!/usr/bin/env python3
"""
match_bili.py —— 把视频列表里的每个条目对上 B 站的真实投稿，拿到链接。

思路：光靠标题匹配不可靠（维基里的标题是当初手抄的，B 站上后来可能改过），
所以用「发布日期 + 标题相似度」两个信号一起判断：

  1. 拉取频道全部投稿（含 bvid、标题、发布时间）
  2. 对每一行，先按日期筛出前后几天的候选
  3. 在候选里挑标题最像的；相似度太低就宁可判为「没找到」
     —— 宁缺毋滥，错配的链接比没有链接更糟

结果写到 bili-videos.json 和 bili-matches.json，供后续步骤使用。
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 王维诗里的MBTI 的 B 站主页（频道信息框里那个）
# 注意别用 1869592347 —— 那是合作方「狐狸刷刷的类型学」的空间
MID = 3493079208168355
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_VIDEOS = os.path.join(HERE, "..", "bili-videos.json")
OUT_MATCHES = os.path.join(HERE, "..", "bili-matches.json")

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Referer": f"https://space.bilibili.com/{MID}",
}


def fetch(url: str, tries: int = 6):
    # 这个接口限流比较凶（code -799），退避要够长，宁可慢也不能把号打得一直 403
    for n in range(tries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
            data = json.loads(raw)
            if data.get("code") == 0:
                return data["data"]
            print(f"    接口返回 code={data.get('code')} {data.get('message')}"
                  f"（第 {n + 1} 次，等 {15 * (n + 1)} 秒）", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"    请求失败：{type(exc).__name__}（第 {n + 1} 次，等 {15 * (n + 1)} 秒）",
                  flush=True)
        time.sleep(15 * (n + 1))
    return None


def collect_videos() -> list[dict]:
    """翻页拉全部投稿。"""
    out: list[dict] = []
    pn = 1
    while True:
        url = (f"https://api.bilibili.com/x/space/arc/search?mid={MID}"
               f"&ps=50&pn={pn}&order=pubdate")
        data = fetch(url)
        if not data:
            break
        page = data.get("page", {})
        vlist = data.get("list", {}).get("vlist", [])
        if not vlist:
            break
        for v in vlist:
            out.append({
                "bvid": v.get("bvid"),
                "title": re.sub(r"<[^>]+>", "", v.get("title", "")),
                "created": v.get("created"),
            })
        print(f"  第 {pn} 页：{len(vlist)} 个（累计 {len(out)}/{page.get('count')}）")
        if len(out) >= (page.get("count") or 0):
            break
        pn += 1
        time.sleep(2)
    return out


def normalize(s: str) -> str:
    """归一化标题，用于比较：统一竖线、去空白、去标点差异。"""
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("｜", "|").replace("！", "!").replace("？", "?")
    s = s.replace("（", "(").replace("）", ")").replace("：", ":")
    s = s.replace("，", ",").replace("、", ",").replace("　", "")
    s = re.sub(r"[\[\]【】《》\s\u200b]", "", s)
    return s.lower()


def match(rows: list[tuple[str, str]], videos: list[dict]) -> list[dict]:
    """rows: [(日期, 标题)] → 每行给出匹配结果与置信度。"""
    by_day: dict[str, list[dict]] = {}
    for v in videos:
        if v.get("created"):
            day = time.strftime("%Y-%m-%d", time.localtime(v["created"]))
            by_day.setdefault(day, []).append(v)

    results = []
    for date, title in rows:
        # 维基里的日期格式：2023年1月13日
        m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date.strip())
        if not m:
            results.append({"date": date, "title": title, "bvid": None, "score": 0.0,
                            "reason": "日期格式不认识"})
            continue
        y, mo, d = (int(x) for x in m.groups())
        base = f"{y:04d}-{mo:02d}-{d:02d}"

        # 前后各放宽几天（首播和维基记录可能差一两天）
        cands = []
        for delta in range(-4, 5):
            try:
                t = time.mktime(time.strptime(base, "%Y-%m-%d")) + delta * 86400
            except ValueError:
                continue
            cands += by_day.get(time.strftime("%Y-%m-%d", time.localtime(t)), [])

        nt = normalize(title)
        best, best_score = None, 0.0
        for c in cands:
            nc = normalize(c["title"])
            score = difflib.SequenceMatcher(None, nt, nc).ratio()
            # 一方包含另一方，说明只是加了后缀 / 截断了，给个加成
            if nt and (nt in nc or nc in nt):
                score = max(score, 0.9)
            if score > best_score:
                best, best_score = c, score

        if best and best_score >= 0.72:
            results.append({"date": date, "title": title, "bvid": best["bvid"],
                            "bili_title": best["title"], "score": round(best_score, 3)})
        else:
            results.append({"date": date, "title": title,
                            "bvid": None, "score": round(best_score, 3),
                            "near": best["title"][:40] if best else None,
                            "reason": "没有够像的候选" if cands else "那天没有投稿"})
    return results


def main() -> int:
    # 从当前 channel.md 里取出表格行
    md = os.path.join(HERE, "..", "src", "content", "docs", "wiki", "channel.md")
    text = open(md, encoding="utf-8").read()
    rows = re.findall(
        r'<td class="wiki-col-date">(.*?)</td><td class="wiki-col-title">(.*?)</td>',
        text, re.S)
    rows = [(a.strip(), re.sub(r"<[^>]+>", "", b).strip()) for a, b in rows]
    print(f"表格数据行：{len(rows)} 条")

    if os.path.exists(OUT_VIDEOS):
        videos = json.load(open(OUT_VIDEOS, encoding="utf-8"))
        print(f"复用已抓取的投稿：{len(videos)} 个（删除 {OUT_VIDEOS} 可重新抓）")
    else:
        print("拉取 B 站投稿列表：", flush=True)
        videos = collect_videos()
        if videos:
            json.dump(videos, open(OUT_VIDEOS, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            print(f"已保存 {len(videos)} 个投稿 → {OUT_VIDEOS}")
        else:
            print("一个都没抓到，不写文件")

    if not videos:
        print("没抓到投稿，退出")
        return 1

    res = match(rows, videos)
    json.dump(res, open(OUT_MATCHES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    hit = [r for r in res if r["bvid"]]
    print(f"\n匹配结果：{len(hit)}/{len(res)} 条找到对应视频")
    print(f"  高置信（≥0.9）：{sum(1 for r in hit if r['score'] >= 0.9)}")
    print(f"  中等（0.72~0.9）：{sum(1 for r in hit if r['score'] < 0.9)}")
    print(f"\n没匹配上的前 8 条：")
    for r in [x for x in res if not x["bvid"]][:8]:
        print(f"  {r['date']:<14} {r['title'][:30]:<32} {r.get('reason', '')}"
              + (f" | 最接近：{r['near']}" if r.get("near") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
