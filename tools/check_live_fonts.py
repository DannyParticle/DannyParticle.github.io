"""轻量线上校验：只看状态码和关键标记，不下载完整字体。"""
import ssl
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

B = "https://dannyparticle.github.io"


def head_or_get(path, limit=0):
    """limit=0 表示只读前若干字节，不断开就早退。"""
    for _ in range(8):
        try:
            req = urllib.request.Request(B + path, headers={"User-Agent": "v"})
            r = urllib.request.urlopen(req, timeout=45, context=ssl.create_default_context())
            data = r.read(limit) if limit else b""
            return r.status, r.headers.get("Content-Length"), data
        except urllib.error.HTTPError as e:
            return e.code, None, b""
        except Exception:  # noqa: BLE001
            time.sleep(8)
    return None, None, b""


print("=== 页面 ===")
for p in ["/", "/wiki/channel/", "/en/", "/en/wiki/channel/", "/en/blog/", "/blog/"]:
    st, _, body = head_or_get(p, 400_000)
    if st != 200:
        print(f"  {p:<22} {st}")
        continue
    h = body.decode("utf-8", "replace")
    print(f"  {p:<22} 200  字体:{'有' if 'font-select' in h else '无'}"
          f"  繁简:{'有' if 'script-select' in h else '无'}"
          f"  语言:{'有' if 'starlight-lang-select' in h else '无'}")

print("\n=== 字体（只看状态和大小，不下载）===")
st, size, _ = head_or_get("/fonts/site-fonts.css", 9000)
print(f"  site-fonts.css  {st}  {int(size or 0) / 1024:.1f} KB")
for name, p in [
    ("霞鹜文楷屏幕阅读版", "/fonts/LXGWWenKaiScreen.woff2"),
    ("MiSans", "/fonts/MiSansVF.ttf"),
    ("HarmonyOS Sans SC", "/fonts/HarmonyOS_Sans_SC_Regular.ttf"),
    ("思源宋体", "/fonts/NotoSerifSC-Regular.woff2"),
]:
    st, size, _ = head_or_get(p, 1)
    mb = int(size or 0) / 1024 / 1024
    print(f"  {name:<18} {st}  {mb:.1f} MB" if st == 200 else f"  {name:<18} {st}  ✗")

print("\n=== 旧的 97 片字体应当 404 ===")
st, _, _ = head_or_get("/fonts/files/lxgwwenkaiscreen-subset-4.woff2", 1)
print(f"  旧分片  {st}  {'（已清除 ✓）' if st == 404 else '（仍在，需检查）'}")
