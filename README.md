# 王维诗里的MBTI · 资料站

bilibili 频道「[王维诗里的MBTI](https://space.bilibili.com/3493079208168355)」的非官方资料站 +
个人博客。内容从 Fandom（`wangweishilidembti.fandom.com`）迁移而来。

在线地址：<https://dannyparticle.github.io/>

- **资料站** `/wiki/*` —— 29 页，由 Astro Starlight 提供侧边栏、目录与全文搜索
- **博客** `/blog/*` —— Astro 内容集合，按分类归档

## 技术栈

| | |
|---|---|
| 框架 | Astro 7 + [Starlight](https://starlight.astro.build) |
| 搜索 | Pagefind（构建时生成索引） |
| 字体 | [霞鹜文楷 屏幕阅读版](https://github.com/lxgw/LxgwWenKai)（自托管，不依赖 CDN） |
| 部署 | GitHub Actions → GitHub Pages |

> 早期版本用 MkDocs Material 构建，已由 Astro 版取代；旧版完整代码在 git 历史里。

## 目录结构

```
src/
├── components/          首页各区块 + 页脚（Astro 组件）
├── content/
│   ├── docs/index.mdx   首页
│   ├── docs/wiki/       资料站 29 篇（Starlight 文档集合）
│   ├── blog/            博客文章（普通内容集合）
│   └── i18n/            界面文案覆盖
├── pages/blog/          博客列表页与文章页
├── styles/custom.css    全部自定义样式（配色、排版、维基组件）
└── content.config.ts    两个内容集合的定义
public/
├── wiki-images/         126 张维基图片
└── fonts/               霞鹜文楷（97 个 woff2 分片，按 unicode-range 按需加载）
tools/                   迁移工具链
dump/                    原始 Fandom 导出 XML（数据备份）
```

## 本地开发

```bash
npm install          # 国内可加 --registry=https://registry.npmmirror.com
npm run dev          # http://localhost:4321
npm run build        # 输出到 dist/
npm run preview      # 预览构建结果
```

## 写博客

在 `src/content/blog/` 下新建 `.md`，frontmatter 写好这几项即可：

```yaml
---
title: 文章标题
date: 2026-09-23
category: 随笔        # 资料站 / 频道动态 / 随笔 / 折腾记
excerpt: 一句话摘要，显示在列表和首页卡片上
cover: /wiki-images/xxx.webp   # 可选，卡片封面
---
```

首页「最新文章」和 `/blog/` 列表都是**构建时自动读取**的，不用手动登记。

## 如何更新资料站内容

内容是从 Fandom 导出后自动转换的，不需要手写。

### 1. 从 Fandom 抓取（需要能访问 Fandom 的网络）

```bash
python tools/archive_wiki.py --base https://wangweishilidembti.fandom.com --out fandom-archive
```

抓取**所有页面**（渲染 HTML + 原始 wikitext）和**所有图片原图**，支持断点续传。
被 Cloudflare 拦截时用 `--cookie "cf_clearance=..."`；加速器是本地代理时用 `--proxy http://127.0.0.1:7890`。

> 也可以用 `tools/browser-archive.js` 在浏览器控制台里一键打包下载（只有浏览器能访问 Fandom 时用这个）。

### 2. wikitext → Markdown

```bash
python tools/mw2md.py --xml dump/xxx.xml --docs build/wiki --images fandom-archive/images
```

处理的语法：信息框模板 → HTML 信息卡、`{| |}` 表格 → Markdown/HTML 表格、
`[[链接]]` → 相对链接、`[[分类:X]]` → front matter 标签、`<gallery>` → 响应式图集、
`''斜体''`/`'''粗体'''`、`== 标题 ==`、`<nowiki>`、`<ref>`、`-{zh-hans:..}-` 语言变体等。

### 3. 适配 Astro

```bash
python tools/to_astro.py --src build/wiki --docs src/content/docs/wiki \
                         --public public --images fandom-archive/images
```

会把图片路径改成站内绝对路径、把 Material 的折叠块换成 `<details>`、
并去掉与 Starlight 页面标题重复的正文 H1。

### 4. 检查并构建

```bash
python tools/check_residual.py src/content/docs/wiki   # 残留学法、死链、缺图
npm run build
```

## 踩过的坑（都记在这，省得再踩）

**图片相对路径要多算一层。** 页面文件是 `docs/wiki/characters/xxx.md`，
但 MkDocs 的 `use_directory_urls` 让实际 URL 变成 `/wiki/characters/xxx/`，比文件路径深一层。
Astro 版改成站内绝对路径 `/wiki-images/...`，彻底绕开。

**Markdown 不会在裸 HTML 块里生效。** 信息卡是 HTML 表格，里面必须写真正的
`<img>` / `<a>` 标签，写 `![](..)` 会原样显示出来。

**浏览器另存网页的文件名会变形。** 中文变 `%3F`、空格变下划线、PNG 存成 webp 缩略图、
重名加 `(1)` 后缀 —— 收拢图片时要归一化匹配（见 `tools/import_archive.py`）。

**无头浏览器截图有最小窗口宽度。** Windows 上 `--window-size=430` 实际按 ~510px 排版再裁切，
看起来像内容被切掉。测手机版要用 iframe 包一层拿真实窄视口（见 `tools/screenshot.ps1`）。

**霞鹜文楷只有 400 一个字重。** 粗体由浏览器合成，楷体合成粗体容易发糊，
所以标题靠字号和颜色拉层次，`font-weight` 用 600 而非 700。

## 许可

维基文字内容整理自原 Fandom 维基，依 **CC BY-SA 3.0** 发布。
角色立绘、频道素材版权归原作者所有，本站仅作资料整理。
