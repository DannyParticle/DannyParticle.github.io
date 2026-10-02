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

## 在线编辑资料站

<https://dannyparticle.github.io/admin/>

一个自己用的编辑器，**只动 `src/content/docs/wiki/` 下的 Markdown**，不需要任何后端：

1. 打开页面，粘贴一个 GitHub Token（classic token，勾 `repo` 权限即可）
2. 左侧选页面 → 中间编辑 → 右侧实时预览
3. 点「保存」→ 通过 GitHub API 提交到仓库 → Actions 自动重建，约 1 分钟生效

功能：新建页面（自动套 frontmatter 模板）、删除、**插入图片**（上传到 `/wiki-images/`
并把标签插到光标处）、`Ctrl+S` 保存、`Tab` 缩进、未保存时关页面会拦一下。

Token 只存在浏览器 `localStorage`（键名 `dsh_wiki_token`），不会上传到任何地方；
点「忘记」即可清除。页面本身没有 token 就什么都做不了，也已在 `robots.txt` 和
`noindex` 里排除索引。

> 编辑器的接口契约可以用 `python tools/test_editor_api.py` 验证
> （列目录 → 新建 → 读回 → 改 → 删除，跑完自动清理）。
> 底部还保留了 Starlight 的「在 GitHub 上编辑」链接，编辑器万一出问题可以兜底。

### 英文版自动同步

中文内容一改，`.github/workflows/sync-en.yml` 会在 GitHub 的机器上跑
`tools/sync_en.py`，**只翻译改动的那几行**，然后把英文提交回来。

为什么是增量而不是重翻：清单 `.en-sync.json` 里同时记着上次同步的**中文原文**和
**英文译文**，两者逐行对应。同步时把「上次的中文」和「这次的中文」做行级 diff，
对齐上的行直接沿用清单里对应的英文 —— 当初那份人工质量的译文不会被动到。
实测加一个视频行是 **+1/−0**，其余 450 行纹丝不动。

几条硬规则（都是踩过坑之后加的）：

- **绝不把中文写进英文文件。** 如果英文与清单里的中文行数对不上（有人绕过同步
  直接改了中文），就退化成「整篇重翻」并告警 —— 宁可质量降一档。
  早先的版本在这种情况下会复制中文过去，把整份英文冲掉，已修。
- **占位符必须用 `{0}`。** 送翻前会把 HTML 标签、URL、行内代码、视频标题换成占位符，
  翻完还原。实测 `⟦0⟧` 会被接口拆成 `⟦0 | xxx⟧`，`{0}` 能原样保留。
  万一还是被拆坏，`finish()` 会抛错而不是把 `{0}` 留在页面上。
- **接口双保险。** 先试 Google 免密钥接口（Actions 在海外能通），失败退 MyMemory。
  两个都不通就整体失败退出，不写入半截内容。
- **视频标题不翻。** 那是 B 站原始标题，翻了既搜不到也对不上。

手动跑：`python tools/sync_en.py`（`--dry-run` 只看哪些文件会变，`--force` 全部重算）。
首次接入或改坏了基线，用 `--init` 把当前中英对照重新记为基线。

> 翻译质量：改动的新行是机器翻译，已有译文保持原样。
> 想整体提质的话，可以让 AI 重新过一遍，然后用 `--init` 重设基线。

## 字体

四套中文字体，**全部完整、不做 unicode-range 分片**。分片虽然省流量，但只要新增
内容里出现一个落在未覆盖区间的字，就会掉到后备字体，看起来像「缺字」——
资料站会长草，这个风险不值得冒。

| 字体 | 文件 | 许可 | 格式 |
|---|---|---|---|
| 霞鹜文楷 屏幕阅读版（默认） | `LXGWWenKaiScreen.woff2` | SIL OFL 1.1 | woff2 |
| MiSans | `MiSansVF.ttf` | 小米自有许可 | TTF 原样 |
| HarmonyOS Sans SC | `HarmonyOS_Sans_SC_Regular.ttf` | 华为自有许可 | TTF 原样 |
| 思源宋体 Noto Serif SC | `NotoSerifSC-Regular.woff2` | SIL OFL 1.1 | woff2 |

**为什么后两个是 TTF 而不是 woff2**：这两家的许可都明文写了「不得修改字体」。
格式转换算不算修改有争议，所以干脆原样发布，一个字节都不动；OFL 的两套才转 woff2
（体积约省一半）。华为的许可还要求「在软件中显著声明使用了 HarmonyOS Sans」，
署名放在页脚。

顶栏的「字」下拉切换字体，选择存在 `localStorage`，并在 `<head>` 里用一段内联脚本
**在首屏渲染前**写进 `<html data-font>` —— 否则回访用户会先看到默认字体再跳一下。

只有被选中的那一套会被下载（后备链里只写系统字体，绝不把另一套网络字体放进去，
否则浏览器会为了补字形把第二套也下了）。

重新生成字体：`python tools/build_fonts.py`（原文件同时在工作区的 `../fonts/` 留档）。

## 多语言

界面语言用 Starlight 内置的 i18n：简体中文在根路径，英文在 `/en/` 下。
顶栏的语言选择器是**按页对应**的 —— 在 `/wiki/channel/` 上选 English 会去
`/en/wiki/channel/`，这和 Fandom 的跨语言链接是同一个思路（每种语言一套独立内容，
页面之间一一挂钩）。资料站的英文内容放在 `src/content/docs/en/wiki/`，
博客英文放在 `src/content/blog-en/`。侧边栏标签用 Starlight 的 `translations` 字段。

**繁简切换**走另一条路：不复制内容，而是在浏览器里用 `opencc-js` 做字形转换，
所以是瞬时的、也不用维护两份。转换会跳过 `<script>` / `<style>` / `<code>` / `<pre>`，
并且记下原始文本，切回简体可以完整还原。

> 英文正文是机器翻译的产物。改中文内容后英文不会自动跟着变，
> 需要重新翻一遍（可以让 AI 批量做）。

## 如何更新资料站内容

### 视频列表怎么维护

频道页的「视频列表」**按年份折叠**，每一块都是普通 Markdown 表格 —— 加一行就是加一行：

`markdown
<details>
<summary>2023 年（41 个）</summary>

| 发布 | 视频标题 | 所属系列 | 备注 |
|---|---|---|---|
| 2023年1月13日 | [16型人格阳了的表现 ｜ 全员向动画](https://www.bilibili.com/video/BV1JW4y137Nt/) | 人格观察室 |  |

</details>
`

要点：

- **标题写成链接**就是可点的视频入口；没有链接就写纯文字
- 标题里的竖线**必须用全角 ｜**，半角 | 是表格列分隔符，会把这一行切断
- 年份块是 <details>，**块、表格、</details> 之间都要留空行**，否则表格不会被解析
- 最新一年不折叠（直接铺开），其余年份默认收起

链接可以自动补：python tools/match_bili.py 拉取 B 站投稿，按「日期 + 标题相似度」
把每行对上真实视频（匹配不上就退回备注里原有的链接，宁缺毋滥）。

> 注意：1869592347 是合作方「狐狸刷刷的类型学」的空间，
> 频道主号是 3493079208168355，别搞混。


日常改内容**直接用 [/admin/ 编辑器](https://dannyparticle.github.io/admin/)** 就行，改完保存，
GitHub Actions 自动重建。下面这套是从 Fandom 重新导出的流程，属于「一次性迁移」，
平时用不到。

> ⚠️ **重跑迁移会覆盖编辑器里改过的内容。** `to_astro.py` 默认会逐个文件比对，
> 内容与源文件不一致（也就是被编辑器改过）的页面**自动跳过**，并在结尾列出来。
> 确认要整体覆盖时才加 `--force`。编辑器里**新建**的页面不在源文件里，脚本也不会去动。

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

**Markdown 表格的单元格里不能有换行。** wikitext 表头常写成 `!正式名/性转` 换行
`（2023年9月15日之后）`，解析出来单元格里带 `\n`；而 Markdown 表格「一行就是一行」——
表头被拆断后整张表会退化成一堆竖线文字。转换时要把单元格压成单行
（`mw2md.py` 的 `md_cell`），`tools/check_residual.py` 里有对应的表格结构自检。

**Starlight 不会替你解析相对 `.md` 链接。** `characters/huzi-intj.md` 会原样进 HTML，
从 `/wiki/channel/` 打开就是 404。必须在转换阶段改写成站点绝对路径
（`to_astro.py` 的 `rewrite_md_links`），并用 `tools/check_links.py` 兜底全站扫一遍。

**浏览器另存网页的文件名会变形。** 中文变 `%3F`、空格变下划线、PNG 存成 webp 缩略图、
重名加 `(1)` 后缀 —— 收拢图片时要归一化匹配（见 `tools/import_archive.py`）。

**无头浏览器截图有最小窗口宽度。** Windows 上 `--window-size=430` 实际按 ~510px 排版再裁切，
看起来像内容被切掉。测手机版要用 iframe 包一层拿真实窄视口（见 `tools/screenshot.ps1`）。

**霞鹜文楷只有 400 一个字重。** 粗体由浏览器合成，楷体合成粗体容易发糊，
所以标题靠字号和颜色拉层次，`font-weight` 用 600 而非 700。

## 许可

维基文字内容整理自原 Fandom 维基，依 **CC BY-SA 3.0** 发布。
角色立绘、频道素材版权归原作者所有，本站仅作资料整理。
