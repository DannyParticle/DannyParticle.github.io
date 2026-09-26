# 用无头 Edge/Chrome 给站点截图，方便改完样式后肉眼验收
#
#   1. 先构建并起一个本地服务：
#        mkdocs build
#        python -m http.server 8123 --bind 127.0.0.1 --directory site
#   2. 另开一个终端跑：
#        powershell -ExecutionPolicy Bypass -File tools/screenshot.ps1
#   3. 截图输出到 _shots/ 目录
#
# ⚠ 坑：Windows 上无头浏览器有约 500px 的最小窗口宽度。
#   --window-size=430 实际会按 ~510px 排版、再裁成 430px 输出，
#   看起来像「内容被切掉」，其实页面本身没问题。
#   所以手机版截图这里改用 iframe 包一层，拿到真正的 430px 视口。

param(
  [string]$Base = "http://127.0.0.1:8123",
  [string]$OutDir = "$PSScriptRoot\..\_shots"
)

$browsers = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)
$browser = $browsers | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { Write-Error "没找到 Edge 或 Chrome"; exit 1 }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Shoot([string]$name, [string]$url, [int]$w, [int]$h) {
  $file = Join-Path $OutDir ($name + ".png")
  if (Test-Path $file) { Remove-Item -Force $file }
  $profile = Join-Path $env:TEMP ("edge-shot-" + [guid]::NewGuid().ToString("N"))
  Start-Process -FilePath $browser -Wait -WindowStyle Hidden -ArgumentList @(
    "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
    "--user-data-dir=$profile", "--window-size=$w,$h",
    "--screenshot=$file", $url
  )
  Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
  if (Test-Path $file) { "  OK   {0,-20} {1,7:N0} KB" -f $name, ((Get-Item $file).Length / 1KB) }
  else { "  FAIL {0}" -f $name }
}

# ---------- 桌面版 ----------
$pages = @(
  @{ n = "home";      p = "/";                            w = 1280; h = 1400 },
  @{ n = "wiki-home"; p = "/wiki/";                       w = 1280; h = 1600 },
  @{ n = "character"; p = "/wiki/characters/haose-istj/"; w = 1280; h = 1900 },
  @{ n = "channel";   p = "/wiki/channel/";               w = 1280; h = 2000 },
  @{ n = "pairings";  p = "/wiki/pairings/";              w = 1280; h = 1300 },
  @{ n = "buqi";      p = "/wiki/works/buqi/";            w = 1280; h = 1300 }
)
foreach ($page in $pages) { Shoot $page.n "$Base$($page.p)" $page.w $page.h }

# ---------- 手机版（iframe 拿真实窄视口） ----------
$mobilePages = @(
  @{ n = "character-mobile"; p = "/wiki/characters/haose-istj/" },
  @{ n = "home-mobile";      p = "/" }
)
foreach ($page in $mobilePages) {
  $tmp = Join-Path $env:TEMP ("mobile-preview-" + [guid]::NewGuid().ToString("N") + ".html")
  $doc = @"
<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;background:#dfe3ee}
iframe{display:block;width:430px;height:1500px;border:0;background:#fff;
margin:1rem;box-shadow:0 6px 24px #0003}</style></head>
<body><iframe src="$Base$($page.p)"></iframe></body></html>
"@
  Set-Content -Path $tmp -Value $doc -Encoding UTF8
  $fileUrl = "file:///" + ($tmp -replace '\\', '/')
  Shoot $page.n $fileUrl 520 1560
  Remove-Item -Force $tmp -ErrorAction SilentlyContinue
}

Write-Host "`n截图目录：$OutDir" -ForegroundColor Green
