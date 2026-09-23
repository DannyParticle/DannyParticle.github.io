# 用无头 Edge/Chrome 给站点截图，方便改完样式后肉眼验收
#
#   1. 先构建并起一个本地服务：
#        mkdocs build
#        python -m http.server 8123 --bind 127.0.0.1 --directory site
#   2. 另开一个终端跑：
#        powershell -ExecutionPolicy Bypass -File tools/screenshot.ps1
#   3. 截图输出到 _shots/ 目录

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

$pages = @(
  @{ n = "home";             p = "/";                            w = 1280; h = 1400 },
  @{ n = "wiki-home";        p = "/wiki/";                       w = 1280; h = 1600 },
  @{ n = "character";        p = "/wiki/characters/haose-istj/"; w = 1280; h = 1900 },
  @{ n = "character-mobile"; p = "/wiki/characters/haose-istj/"; w = 430;  h = 1400 },
  @{ n = "channel";          p = "/wiki/channel/";               w = 1280; h = 2000 },
  @{ n = "pairings";         p = "/wiki/pairings/";              w = 1280; h = 1300 },
  @{ n = "buqi";             p = "/wiki/works/buqi/";            w = 1280; h = 1300 }
)

foreach ($page in $pages) {
  $file = Join-Path $OutDir ($page.n + ".png")
  if (Test-Path $file) { Remove-Item -Force $file }
  $args = @(
    "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
    "--user-data-dir=$env:TEMP\edge-shot-profile",
    "--window-size=$($page.w),$($page.h)",
    "--screenshot=$file", "$Base$($page.p)"
  )
  Start-Process -FilePath $browser -ArgumentList $args -Wait -WindowStyle Hidden
  if (Test-Path $file) {
    "  OK   {0,-18} {1,7:N0} KB" -f $page.n, ((Get-Item $file).Length / 1KB)
  } else {
    "  FAIL {0}" -f $page.n
  }
}

Write-Host "`n截图目录：$OutDir" -ForegroundColor Green
