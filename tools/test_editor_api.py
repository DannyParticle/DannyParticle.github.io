#!/usr/bin/env python3
"""
验证资料站编辑器依赖的 GitHub API 契约。

编辑器是纯前端 + GitHub API，没法在无头浏览器里方便地驱动，
所以这里用它调用的**同一组接口**做一次真实往返：
  列目录 → 新建 → 读回 → 改 → 删除
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN = os.environ.get("GH_TOKEN", "").strip()
OWNER, REPO, BRANCH = "DannyParticle", "DannyParticle.github.io", "main"
WIKI_DIR = "src/content/docs/wiki/"
TEST_PATH = WIKI_DIR + "_editor-contract-test.md"


def api(path: str, method: str = "GET", body: dict | None = None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "editor-contract-test",
            **({"Content-Type": "application/json"} if body else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=ssl.create_default_context()) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


ok = fail = 0


def check(label: str, cond: bool, extra: str = ""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {label}{('　' + extra) if extra else ''}")
    else:
        fail += 1
        print(f"  ✗ {label}　{extra}")


# 1. 文件列表（编辑器左侧目录树用的接口）
st, tree = api(f"/repos/{OWNER}/{REPO}/git/trees/{BRANCH}?recursive=1")
files = [n["path"] for n in tree.get("tree", [])
         if n["type"] == "blob" and n["path"].startswith(WIKI_DIR) and n["path"].endswith(".md")]
check("列出资料站页面", st == 200 and len(files) >= 29, f"{len(files)} 个")

# 2. 新建（编辑器「新建」按钮的写入路径）
content = '---\ntitle: "契约测试"\n---\n\n这是一个临时文件，测试完会删掉。\n'
st, created = api(f"/repos/{OWNER}/{REPO}/contents/{TEST_PATH}", "PUT", {
    "message": "编辑器契约测试：新建",
    "content": base64.b64encode(content.encode()).decode(),
    "branch": BRANCH,
})
check("新建页面", st in (200, 201), f"HTTP {st} {created.get('message', '')}")
sha = created.get("content", {}).get("sha")

# 3. 读回（编辑器打开文件用的接口）
st, got = api(f"/repos/{OWNER}/{REPO}/contents/{TEST_PATH}?ref={BRANCH}")
decoded = base64.b64decode(got.get("content", "")).decode() if st == 200 else ""
check("读回内容一致", decoded == content, f"{len(decoded)} 字节")

# 4. 修改（保存已有文件要带 sha）
new_content = content.replace("临时文件", "已修改的临时文件")
st, updated = api(f"/repos/{OWNER}/{REPO}/contents/{TEST_PATH}", "PUT", {
    "message": "编辑器契约测试：修改",
    "content": base64.b64encode(new_content.encode()).decode(),
    "sha": sha,
    "branch": BRANCH,
})
check("带 sha 覆盖保存", st in (200, 201), f"HTTP {st}")
sha2 = updated.get("content", {}).get("sha")

# 5. 删除
st, deleted = api(f"/repos/{OWNER}/{REPO}/contents/{TEST_PATH}", "DELETE", {
    "message": "编辑器契约测试：删除",
    "sha": sha2,
    "branch": BRANCH,
})
check("删除页面", st == 200, f"HTTP {st}")

# 6. 确认删干净
st, again = api(f"/repos/{OWNER}/{REPO}/contents/{TEST_PATH}?ref={BRANCH}")
check("确认已删除", st == 404, f"HTTP {st}")

print(f"\n通过 {ok}/{ok + fail}")
