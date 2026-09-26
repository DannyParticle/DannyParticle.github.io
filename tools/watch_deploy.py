#!/usr/bin/env python3
"""等 GitHub Actions 跑完，并报告结果。"""
from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TOKEN = os.environ.get("GH_TOKEN", "").strip()
REPO = "DannyParticle/DannyParticle.github.io"
DEADLINE = time.time() + float(os.environ.get("WAIT_SECONDS", "420"))


def get(path: str):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "watch"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=ssl.create_default_context()) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


last = None
while True:
    st, data = get(f"/repos/{REPO}/actions/runs?per_page=1")
    runs = data.get("workflow_runs", []) if st == 200 else []
    if runs:
        r = runs[0]
        line = f"#{r['run_number']} {r['status']} {r['conclusion']} ({r['head_sha'][:7]})"
        if line != last:
            print(f"[{time.strftime('%H:%M:%S')}] {line}", flush=True)
            last = line
        if r["status"] == "completed":
            print(f"\n工作流结论：{r['conclusion']}")
            if r["conclusion"] != "success":
                print(f"详情：{r['html_url']}")
            break
    if time.time() > DEADLINE:
        print("等待超时")
        break
    time.sleep(12)

st, pages = get(f"/repos/{REPO}/pages")
if st == 200:
    print(f"Pages：{pages.get('html_url')}（构建方式 {pages.get('build_type')}）")
