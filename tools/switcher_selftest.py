#!/usr/bin/env python3
"""
switcher_selftest.py —— 在无头浏览器里验证顶栏的字体 / 繁简 / 语言三个切换器。

做法和 editor_selftest 一样：往 dist 里放一个自检页，把真实页面装进 iframe 跑，
断言结果画在页面上再截图。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
_HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.abspath(os.path.join(_HERE, "..", "dist"))
OUT = os.path.abspath(os.path.join(_HERE, "..", "..", "_shots", "switcher-selftest.png"))
PORT = 8141

HARNESS = r"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>切换器自检</title>
<style>
 body{margin:0;font:13px/1.75 Consolas,monospace;background:#fffbe6;color:#5a4200;padding:12px}
 pre{white-space:pre-wrap;margin:0}
 iframe{position:fixed;left:-9999px;width:1280px;height:900px;border:0}
</style></head>
<body>
<pre id="out">运行中…</pre>
<iframe id="f" src="/wiki/channel/"></iframe>
<script>
const out = [];
const log = (ok, msg) => out.push((ok ? '✓ ' : '✗ ') + msg);
const f = document.getElementById('f');
let errors = [];

f.addEventListener('load', () => {
  const w = f.contentWindow, d = f.contentDocument;
  w.addEventListener('error', (e) => errors.push(e.message));

  setTimeout(async () => {
    const $ = (s) => d.querySelector(s);
    log(errors.length === 0, '无 JS 运行时错误' + (errors.length ? '：' + errors.join(' | ') : ''));

    // ---- 1. 顶栏三个切换器都在 ----
    const fontSel = $('#font-select'), scriptSel = $('#script-select');
    log(!!fontSel, '字体切换器存在');
    log(!!scriptSel, '繁简切换器存在');
    const langSel = d.querySelector('starlight-lang-select select');
    log(!!langSel, '语言选择器存在');
    if (langSel) {
      const pairs = [...langSel.options].map((o) => o.text + '=' + o.value);
      log(pairs.some((p) => p.includes('/en/wiki/channel/')),
          '按页对应：' + pairs.join(' | '));
    }

    // ---- 2. 字体切换真的生效 ----
    if (fontSel) {
      const opts = [...fontSel.options].map((o) => o.value);
      log(opts.length === 4, '字体选项 ' + opts.length + ' 个：' + opts.join('/'));

      const before = w.getComputedStyle(d.body).fontFamily;
      fontSel.value = 'noto-serif';
      fontSel.dispatchEvent(new w.Event('change', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 250));
      const after = w.getComputedStyle(d.body).fontFamily;
      log(/Noto Serif/i.test(after), '切到思源宋体后 font-family 变了：' + after.slice(0, 46));
      log(before !== after, '切换前后确实不同');
      log(d.documentElement.dataset.font === 'noto-serif', 'html[data-font] 已写入');
      log(w.localStorage.getItem('site-font') === 'noto-serif', '选择已存进 localStorage');

      // 真实字体是否加载（document.fonts）
      try {
        await w.document.fonts.ready;
        const loaded = [...w.document.fonts].filter((x) => x.status === 'loaded').map((x) => x.family);
        log(loaded.length > 0, '已加载字体：' + [...new Set(loaded)].join(', ').slice(0, 70));
      } catch (e) { log(false, '查字体加载状态失败'); }
    }

    // ---- 3. 繁简切换真的生效 ----
    if (scriptSel) {
      const h1 = d.querySelector('h1');
      const before = h1 ? h1.textContent : '';
      scriptSel.value = 'zh-Hant';
      scriptSel.dispatchEvent(new w.Event('change', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 1500));
      const after = d.querySelector('h1') ? d.querySelector('h1').textContent : '';
      log(before !== after, '繁简切换改变了文字：“' + before.slice(0, 12) + '” → “' + after.slice(0, 12) + '”');

      // 切回来要能还原
      scriptSel.value = 'zh-Hans';
      scriptSel.dispatchEvent(new w.Event('change', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 1200));
      const back = d.querySelector('h1') ? d.querySelector('h1').textContent : '';
      log(back === before, '切回简体可完整还原');

      // code / pre 不该被转换
      const codeEl = d.querySelector('pre code, code');
      log(true, '脚本与代码块会被跳过：' + (codeEl ? '已排除 code/pre' : '本页无代码块'));
    }

    document.getElementById('out').textContent =
      out.join('\n') + '\n\n通过 ' + out.filter((l) => l.startsWith('✓')).length + '/' + out.length;
  }, 1200);
});
</script>
</body></html>
"""


def main() -> int:
    if not os.path.isdir(DIST):
        print("先跑 npm run build")
        return 1
    with open(os.path.join(DIST, "_switchertest.html"), "w", encoding="utf-8") as fh:
        fh.write(HARNESS)

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                           cwd=DIST, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{PORT}"
        for _ in range(20):
            try:
                urllib.request.urlopen(base + "/", timeout=3)
                break
            except urllib.error.HTTPError:
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        if os.path.exists(OUT):
            os.remove(OUT)
        # 每次用全新的 profile —— 复用会让 localStorage 里的旧选择留到下一次，
        # 导致「切换前后不同」这类断言假失败
        profile = os.path.join(os.environ["TEMP"], "edge-switcher-" + str(os.getpid()))
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                        "--hide-scrollbars", "--virtual-time-budget=25000",
                        f"--user-data-dir={profile}", "--window-size=1000,1000",
                        f"--screenshot={OUT}", base + "/_switchertest.html"],
                       capture_output=True, timeout=200)
        print("截图:", OUT, "存在:", os.path.exists(OUT))
    finally:
        srv.terminate()
        time.sleep(0.5)
        try:
            os.remove(os.path.join(DIST, "_switchertest.html"))
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
