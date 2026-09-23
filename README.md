# 王维诗里的MBTI · 资料站

bilibili 频道「[王维诗里的MBTI](https://space.bilibili.com/3493079208168355)」的非官方资料维基，
从 Fandom（`wangweishilidembti.fandom.com`）迁移而来，使用 MkDocs Material 构建并发布在 GitHub Pages。

在线地址：<https://dannyparticle.github.io/>

## 站点结构

```
docs/
├── index.md                      站点首页
├── blog/index.md                 博客分区（待填充）
├── tags.md                       标签索引
├── stylesheets/extra.css         信息框、画廊、表格样式
├── assets/wiki-images/           维基图片（由抓取脚本产出）
└── wiki/
    ├── index.md                  维基首页（角色卡片导航）
    ├── about.md                  关于本维基
    ├── channel.md                频道介绍（成员、角色表、视频列表）
    ├── pairings.md               各 MBTI 排列组合
    ├── studio.md                 工作室
    ├── characters/               16 位角色的档案
    ├── people/                   运营者与合作博主
    ├── theory/                   荣格理论和荣格八维
    └── works/                    《不器》、B站二创
```

## 本地预览

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
mkdocs serve                     # 打开 http://127.0.0.1:8000
```

构建静态文件：

```bash
mkdocs build                     # 输出到 site/
```

## 部署

推送到 `main` 分支后，GitHub Actions（`.github/workflows/deploy.yml`）会自动构建并发布到 GitHub Pages。
仓库的 **Settings → Pages → Source** 需要选择 **GitHub Actions**。

## 如何更新维基内容

内容是从 Fandom 导出后自动转换的，不需要手写。完整流程：

### 1. 从 Fandom 抓取（需要能访问 Fandom 的网络）

```bash
python tools/archive_wiki.py \
    --base https://wangweishilidembti.fandom.com \
    --out fandom-archive
```

这一步会把**所有页面**（渲染后的 HTML + 原始 wikitext）和**所有图片原图**抓到 `fandom-archive/`，
支持断点续传，中断后重跑即可。若被 Cloudflare 拦截，用 `--cookie "cf_clearance=..."` 传入浏览器 Cookie；
若加速器是本地代理，用 `--proxy http://127.0.0.1:7890`。

> 也可以只用 Fandom 的 `Special:Export` 导出 XML，但那样拿不到图片。

### 2. 把 wikitext 转成 Markdown

```bash
python tools/mw2md.py \
    --xml dump/zhwangweishilidembti_pages_current.xml \
    --docs web/docs/wiki \
    --images fandom-archive/images \
    --report conversion-report.md
```

转换器处理的语法：信息框模板 → HTML 信息卡、`{| |}` 表格 → Markdown/HTML 表格、
`[[链接]]` → 相对链接、`[[分类:X]]` → front matter 标签、`<gallery>` → 响应式图集、
`''斜体''`/`'''粗体'''`、`== 标题 ==`、`<nowiki>`、`<ref>`、`-{zh-hans:..}-` 语言变体等。

### 3. 检查并构建

```bash
python tools/check_residual.py web/docs/wiki   # 检查残留的 wikitext 标记、死链、缺图
cd web && mkdocs build
```

## 说明

- 维基文字内容整理自原 Fandom 维基，依 **CC BY-SA 3.0** 许可发布。
- 角色立绘、频道素材等版权归原作者所有，本站仅作资料整理。
- 迁移工具链（`tools/`）与站点源码一并放在仓库里，内容可随时重新生成。
