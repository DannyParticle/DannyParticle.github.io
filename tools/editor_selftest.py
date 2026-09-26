#!/usr/bin/env python3
"""
editor_selftest.py — 在无头浏览器里真跑一遍资料站编辑器，检查：

  · 有没有 JS 运行时错误
  · 关键 DOM 是否齐全、内联脚本是否真的执行了
  · 安全措施是否生效（CSP / 沙箱 / referrer / noindex）
  · 预览 iframe 能否渲染，且正文里的 <script> 会被剥掉

做法：往 dist 里放一个自检页，把 /admin/ 装进 iframe 跑，把结果画在页面上再截图。
（无头浏览器不方便直接驱动页面脚本，这样最省事。）
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
DIST = os.path.abspath("wiki-migration/web/dist")
OUT = os.path.abspath("wiki-migration/_shots/editor-selftest.png")
PORT = 8129

HARNESS = r"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>编辑器自检</title>
<style>
  body{margin:0;font:13px/1.7 Consolas,monospace;background:#fffbe6;color:#5a4200;padding:12px}
  pre{white-space:pre-wrap;margin:0}
  iframe{position:fixed;left:-9999px;width:1200px;height:800px;border:0}
</style></head>
<body>
<pre id="out">运行中…</pre>
<iframe id="f" src="/admin/"></iframe>
<script>
const out = [];
const log = (ok, msg) => out.push((ok ? '✓ ' : '✗ ') + msg);
const f = document.getElementById('f');
let errors = [];
f.addEventListener('load', () => {
  const w = f.contentWindow, d = f.contentDocument;
  w.addEventListener('error', (e) => errors.push(e.message));
  setTimeout(() => {
    const $ = (s) => d.querySelector(s);
    log(errors.length === 0, '无 JS 运行时错误' + (errors.length ? '：' + errors.join(' | ') : ''));
    ['#token', '#connect', '#lock', '#tree', '#md', '#pv', '#save', '#summary',
     '#editorBar', '#historyPanel', '#settingsPanel', '#dlgLink', '#dlgTable', '#dlgImage']
      .forEach((s) => log(!!$(s), '存在元素 ' + s));
    const counter = ($('#counter') || {}).textContent || '';
    log(/字符/.test(counter), '内联脚本已执行（#counter = "' + counter + '"）');
    const btns = d.querySelectorAll('#editorBar button[data-act]').length;
    log(btns >= 14, '工具栏按钮 ' + btns + ' 个');
    const csp = d.querySelector('meta[http-equiv="Content-Security-Policy"]');
    log(!!csp && /api\.github\.com/.test(csp.content), 'CSP 限制 connect-src 为 api.github.com');
    const sb = $('#pv').getAttribute('sandbox') || '';
    log(!/allow-scripts/.test(sb), '预览 iframe 禁止脚本（sandbox="' + sb + '"）');
    log((d.querySelector('meta[name="referrer"]') || {}).content === 'no-referrer', 'referrer 为 no-referrer');
    log(((d.querySelector('meta[name="robots"]') || {}).content || '').includes('noindex'), 'robots noindex');

    const md = $('#md');
    md.value = '# 标题\n\n<script>window.__XSS=1<\/script>\n\n**粗体内容**\n';
    md.dispatchEvent(new w.Event('input', { bubbles: true }));
    setTimeout(() => {
      let doc = null;
      try { doc = $('#pv').contentDocument; } catch (e) {}
      log(!!doc, '预览 iframe 可访问（同源）');
      const html = doc && doc.body ? doc.body.innerHTML : '';
      log(html.length > 0, '预览已渲染（' + html.length + ' 字节）');
      log(!/<script/i.test(html), '预览里的 <script> 已被剥离');
      log(!w.__XSS, '注入的脚本没有执行');
      log(/粗体内容/.test(html), 'Markdown 正常渲染');
      document.getElementById('out').textContent =
        out.join('\n') + '\n\n通过 ' + out.filter((l) => l.startsWith('✓')).length + '/' + out.length;
    }, 600);
  }, 900);
});
</script>
</body></html>
"""


def wait_server(url: str, tries: int = 20) -> bool:
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=3)
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def main() -> int:
    if not os.path.isdir(DIST):
        print("先跑 npm run build")
        return 1
    with open(os.path.join(DIST, "_selftest.html"), "w", encoding="utf-8") as fh:
        fh.write(HARNESS)

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                           cwd=DIST, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{PORT}"
        if not wait_server(base + "/"):
            print("本地服务起不来")
            return 1
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        if os.path.exists(OUT):
            os.remove(OUT)
        profile = os.path.join(os.environ["TEMP"], "edge-selftest")
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                        "--hide-scrollbars", "--virtual-time-budget=15000",
                        f"--user-data-dir={profile}", "--window-size=1000,900",
                        f"--screenshot={OUT}", base + "/_selftest.html"],
                       capture_output=True, timeout=180)
        print("自检截图:", OUT, "存在:", os.path.exists(OUT))
    finally:
        srv.terminate()
        time.sleep(0.5)
        try:
            os.remove(os.path.join(DIST, "_selftest.html"))
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
