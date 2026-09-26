---
title: 从零搭一个博客：Astro + GitHub Pages 手把手
date: 2026-09-26
category: 折腾记
excerpt: 不用服务器、不花一分钱，把博客搭在 GitHub 上。从装环境到发布第一篇文章，每一步都写清楚。
cover: /covers/build-a-blog.png
---

一直想有个自己的地方写东西，试过几个博客平台，最后决定自己搭一个。

这篇把整个过程记下来，**假设你完全没接触过，跟着做就行**。全程不用买服务器、不用买域名，花费 0 元。

最终效果就是这个站：有首页、有文章列表、有分类、能搜索，写文章只要丢一个文件进去。

---

## 一、先说清楚这东西的原理

传统的博客（比如 WordPress）是这样的：内容存在**数据库**里，访客打开网页时，服务器去数据库查出来、拼成页面发给你。所以你得租服务器、装环境、定期备份、还得防着被攻击。

这套方案完全不一样：

```
你写 .md 文件  →  提交到 GitHub  →  GitHub 自动编译成 HTML  →  访客看到静态页面
```

**关键区别**：编译这一步只在"你提交的时候"发生一次，生成的是纯 HTML 文件。访客打开网页时没有任何计算，就是把现成的文件发过去。

好处很实在：

- 不需要服务器，也不用维护
- 快 —— 没有数据库查询
- 便宜 —— GitHub Pages 免费
- 内容就是你自己的文件，随时能搬走

坏处也说清楚：**没有后台**（但可以用编辑器解决）、**评论要另接**、**内容多了构建会慢一点**（几千篇以内无所谓）。

---

## 二、要准备什么

三样东西：

1. **一个 GitHub 账号** —— 免费注册
2. **Node.js** —— 官网下 LTS 版，一路下一步装上，装完在终端敲 `node -v` 能看到版本号就行
3. **一个能编辑文本的工具** —— VS Code 最好用，记事本也不是不行

就这些。不需要买域名（GitHub 会送你一个 `你的用户名.github.io`），不需要服务器。

---

## 三、创建项目

打开终端（Windows 是 PowerShell），进到你放代码的目录，然后：

```bash
npm create astro@latest my-blog -- --template starlight
```

这一行会自动下载 Astro 的项目模板。中途它会问你几个问题，都选默认（回车）就行。

`--template starlight` 的意思是"用 Starlight 这个主题"—— 它是 Astro 官方的文档主题，自带侧边栏和搜索，拿来当博客底子很合适。

然后进去装依赖：

```bash
cd my-blog
npm install
```

> 国内网络如果慢，可以加镜像：`npm install --registry=https://registry.npmmirror.com`

装完跑起来看看：

```bash
npm run dev
```

终端会给你一个地址（通常是 `http://localhost:4321`），浏览器打开，能看到一个默认页面，就说明环境通了。

---

## 四、改成你自己的信息

打开 `astro.config.mjs`，这是整个站点的配置文件。先把这几项改成你自己的：

```js
export default defineConfig({
  site: 'https://你的用户名.github.io',
  integrations: [
    starlight({
      title: '我的博客',
      description: '记录一些有的没的',
    }),
  ],
});
```

`site` 这项**必须填对**，它决定后面生成的链接和站点地图。

---

## 五、写第一篇文章

在 `src/content/blog/` 目录下新建一个文件，比如 `hello.md`：

```markdown
---
title: 你好，世界
date: 2026-09-26
category: 随笔
excerpt: 第一篇文章，试试看。
---

这里是正文。用 Markdown 写，比如：

## 这是二级标题

- 列表项
- 另一个列表项

**加粗**、*斜体*、[链接](https://example.com)，都照常写。
```

保存。就这么简单 —— **文件放进去就算发布**，不需要任何"发布"操作。

开头那几行（`---` 包起来的部分）叫 **frontmatter**，是这篇文章的元数据：

| 字段 | 作用 | 必填 |
|---|---|---|
| `title` | 文章标题 | ✅ |
| `date` | 日期，决定排序 | ✅ |
| `category` | 分类，用来分组 | 可不填，默认「随笔」 |
| `excerpt` | 摘要，显示在列表和首页卡片上 | 可选 |
| `cover` | 封面图路径 | 可选 |
| `draft` | 写 `true` 就不发布 | 可选 |

这些字段不是随便定的，得先在配置里声明（下一节讲）。

---

## 六、让 Astro 认识你的文章

打开 `src/content.config.ts`，加上这一段：

```ts
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

export const collections = {
  blog: defineCollection({
    loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
    schema: z.object({
      title: z.string(),
      date: z.coerce.date(),
      category: z.string().default('随笔'),
      excerpt: z.string().optional(),
      cover: z.string().optional(),
      draft: z.boolean().default(false),
    }),
  }),
};
```

这就是上面表格里那些字段的"声明"。Astro 靠它知道 `src/content/blog/` 里的文件是一篇文章，并且会**帮你检查**：标题漏了、日期写错了格式，构建时会直接报错，而不是悄悄显示成空白。

> 这个叫「内容集合」（content collection）。`z` 是数据校验库 zod，`z.string()` 表示"必须是文字"，`.optional()` 表示"可以不填"，`.default('随笔')` 表示"不填就用这个值"。

---

## 七、三个页面撑起整个博客

现在文章有了，但还没有页面展示它。博客其实只需要三个页面：

### 1. 文章列表页

新建 `src/pages/blog/index.astro`：

```astro
---
import { getCollection } from 'astro:content';

const posts = (await getCollection('blog', ({ data }) => !data.draft))
  .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());
---

<h1>全部文章</h1>
<ul>
  {posts.map((p) => (
    <li>
      <a href={`/blog/${p.id}/`}>
        {p.data.date.toISOString().slice(0, 10)} —— {p.data.title}
      </a>
    </li>
  ))}
</ul>
```

两行关键代码解释一下：

- `getCollection('blog', ...)` —— 把 `src/content/blog/` 里的文章全读出来，过滤掉草稿
- `.sort(...)` —— 按日期倒序，新的在前

### 2. 文章详情页

新建 `src/pages/blog/[...slug].astro`：

```astro
---
import { getCollection, render } from 'astro:content';

export async function getStaticPaths() {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  return posts.map((post) => ({ params: { slug: post.id }, props: { post } }));
}

const { post } = Astro.props;
const { Content } = await render(post);
---

<h1>{post.data.title}</h1>
<p>{post.data.date.toISOString().slice(0, 10)} · {post.data.category}</p>
<article><Content /></article>
```

文件名里的 `[...slug]` 是**通配路由**：`hello.md` 会自动变成 `/blog/hello/`，`foo.md` 变成 `/blog/foo/`。

`getStaticPaths()` 的作用是"有几篇文章，就生成几个 HTML 页面"。**这就是"加个文件就等于发布"的原因** —— 你不需要手动登记任何东西。

`<Content />` 负责把 Markdown 正文渲染成 HTML。

### 3. 首页的最新文章

首页不用自己写列表，抽成一个组件 `src/components/LatestPosts.astro`：

```astro
---
import { getCollection } from 'astro:content';

const posts = (await getCollection('blog', ({ data }) => !data.draft))
  .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf())
  .slice(0, 3);          // ← 只取最新 3 篇
---
<section>
  <h2>最新文章</h2>
  {posts.map((p) => (
    <a href={`/blog/${p.id}/`}>
      <h3>{p.data.title}</h3>
      <p>{p.data.excerpt}</p>
    </a>
  ))}
</section>
```

注意它和列表页是**同一个查询**，只多了个 `.slice(0, 3)`。所以以后你发了新文章，**首页会自动更新**，不用手动改。

然后把它放进首页（`src/content/docs/index.mdx`）：

```mdx
import LatestPosts from '../../components/LatestPosts.astro';

<LatestPosts />
```

---

## 八、调外观

样式都写在 `src/styles/custom.css` 里，通过 `astro.config.mjs` 注册：

```js
starlight({
  customCss: ['./src/styles/custom.css'],
});
```

几个最影响观感的调整：

**① 改主题色。** Starlight 用 CSS 变量控制配色，覆盖掉就行：

```css
:root {
  --sl-color-accent-low: #ece8f9;
  --sl-color-accent: #6d5bd0;      /* 主色 */
  --sl-color-accent-high: #3a2d78;
}
```

**② 中文排版。** 默认排版是按英文调的，中文会显得挤：

```css
:root {
  --sl-text-base: 1.02rem;   /* 字号大一点 */
  --sl-line-height: 1.85;    /* 行距松一点 */
}

.sl-markdown-content p {
  margin-block: 1.1em;       /* 段间距 */
}
```

**③ 卡片、圆角、阴影。** 这些纯看个人喜好，用统一变量方便全局调：

```css
:root {
  --site-radius: 12px;
  --site-shadow: 0 1px 2px #1a1a2e0a, 0 4px 14px #1a1a2e0d;
}
```

---

## 九、换个好看的中文字体（可选但很值）

系统自带的黑体看久了很寡淡。我用的是**霞鹜文楷**（开源免费，楷体质感，很适合中文博客）。

**第一个坑：字体文件很大。** 全量 4.87 MB，让访客下载完再看网页是不可接受的。

**解法是 `unicode-range` 分片。** 霞鹜文楷有现成的 npm 包，已经把字体切成了 97 个小文件，每个文件只装一部分汉字：

```bash
npm install lxgw-wenkai-screen-webfont
```

把这个包的 `css` 和 `files/` 目录复制到 `public/fonts/` 下，然后在配置里引入：

```js
starlight({
  head: [
    { tag: 'link', attrs: { rel: 'stylesheet', href: '/fonts/wenkai.css' } },
  ],
});
```

浏览器会根据页面上实际出现的字，**只下载用到的那几片**（一片约 7 KB）。中文博客首屏一般加载十几片，不到 100 KB，完全可以接受。

最后在 CSS 里用它：

```css
:root {
  --sl-font: "LXGW WenKai Screen", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}
```

> **第二个坑**：霞鹜文楷**只有一个字重（400）**。如果你给标题设 `font-weight: 700`，浏览器会"合成"一个假粗体，楷体合成粗体容易发糊。把标题改成 `600`，或者干脆靠字号和颜色拉开层次会更好看。
>
> **第三个坑**：不要把字体挂在 jsDelivr 之类的 CDN 上。国内访问不稳定，字体又是首屏资源 —— 挂了就是一大片空白。自己托管最稳。

---

## 十、搜索是白送的

Starlight 内置 Pagefind 搜索，**不用配任何东西**，构建时会自动扫描所有页面生成索引，右上角的搜索框直接就能用（`Ctrl + K`）。

搜索完全在浏览器里跑，不需要任何搜索服务。

---

## 十一、发布到 GitHub Pages

这是最后一步，也是最容易卡住的一步。

### 1. 建仓库并推送

在 GitHub 上新建一个仓库。**名字有讲究**：

- 想访问地址是 `https://你的用户名.github.io` → 仓库名必须叫 `你的用户名.github.io`
- 其他名字也行，但地址会变成 `https://你的用户名.github.io/仓库名/`

建好后在本地项目里执行：

```bash
git init -b main
git add -A
git commit -m "第一版"
git remote add origin git@github.com:你的用户名/仓库名.git
git push -u origin main
```

> 用 SSH 方式（`git@github.com:...`）比 HTTPS 稳，大陆网络尤其明显。第一次用要先在 GitHub 设置里配好 SSH 公钥。

### 2. 加一个自动构建脚本

在项目里新建 `.github/workflows/deploy.yml`，内容：

```yaml
name: 构建并部署到 GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
      - run: npm install --no-audit --no-fund
      - run: npm run build
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

这段的意思：**每次往 `main` 分支推送，GitHub 就在它自己的服务器上跑一遍构建，然后把产物发布出去。** 你不用管，也不用本地构建。

几个容易踩的点：

- `permissions` 那三行**不能省**，否则没有权限发布
- `npm install` 我故意没用 `npm ci` —— 有些包（比如 sharp）带平台相关的二进制，本地是 Windows、构建机是 Linux，用 `ci` 可能因为 lockfile 不匹配直接失败
- `path: dist` 要和 Astro 的输出目录一致（Astro 默认就是 `dist`）

### 3. 打开 Pages

推上去之后，去仓库的 **Settings → Pages**，把 **Source 改成 `GitHub Actions`**。

然后回到仓库的 **Actions** 标签页，应该能看到一个正在跑的任务。绿了就说明成功了，访问 `https://你的用户名.github.io` 就能看到你的博客。

之后每次推送，都会自动重新构建，大约一分钟生效。

---

## 十二、绑自己的域名（可选）

不想用 `github.io` 的话：

1. 买个域名，在 DNS 里加一条 `CNAME` 记录，指向 `你的用户名.github.io`
2. 在仓库 Settings → Pages → Custom domain 里填上你的域名
3. 勾上 `Enforce HTTPS`

**但国内访问 GitHub Pages 本身就不太稳定**，想更快的话，通常的做法是把域名 DNS 托管到 Cloudflare 做一层加速。这块坑不少，改天单独写。

---

## 十三、日常怎么发文章

配好之后，写文章就三步：

**① 新建文件** —— `src/content/blog/文章名.md`

**② 写好开头几行**：

```markdown
---
title: 文章标题
date: 2026-09-26
category: 随笔
excerpt: 一句话摘要
---
```

**③ 推送**：

```bash
git add -A
git commit -m "新文章"
git push
```

等一分钟，线上就有了。列表、分类、首页、搜索索引、站点地图**全部自动更新**。

---

## 十四、我有现成的 HTML，怎么放进去

经常会有这种情况：自己写了个小工具、做了个页面、或者从别处抄了一段 HTML 想要用上。分四种情况说。

### 情况 1：一段 HTML 片段，想插在文章中间

Markdown **本来就支持直接写 HTML**，贴在文章里就行：

```markdown
这是普通段落。

<div style="padding: 12px; border-left: 3px solid #6d5bd0; background: #f6f5fb;">
  这是一个自己写的提示框。
</div>

这又是普通段落。
```

**⚠️ 但这里有个大坑**：HTML 块**内部的 Markdown 不会生效**。

```markdown
<div class="tip">
这段 **不会**变粗 —— 会原样显示两个星号。
</div>

这段 **会**变粗 —— 因为空行让它回到了 Markdown 语境。
```

原因是 Markdown 解析器看到 `<div>` 之后，会把整块当作"原文"原样输出，不再解析里面的语法。这个坑我在做维基信息卡的时候踩得很结实 —— 卡片里的图片和链接全都显示成了源码。

**两个解法：**

**解法 A：HTML 块里就用纯 HTML，别混 Markdown**

```markdown
<div class="tip">
  <strong>加粗</strong>、<a href="/blog/">链接</a>、<img src="/covers/x.png" alt="">
</div>
```

**解法 B：混着写就把每个元素单独成行**

```markdown
<div class="tip">

这里可以写 **Markdown**，因为前后都有空行。

</div>
```

> 用到的 CSS 类名要自己在 `src/styles/custom.css` 里定义，HTML 本身只负责结构。

### 情况 2：一个完整的 HTML 页面（自己写的工具、demo、游戏）

这个最简单 —— **直接把文件丢进 `public/` 目录**。

`public/` 里的东西会被**原样复制**到网站根目录，不做任何处理。所以：

```
public/demo/index.html   →  访问 https://你的域名/demo/
public/tool.html         →  访问 https://你的域名/tool.html
```

比如你写了个单文件的计算器 `public/calc/index.html`，里面引用了同目录的 `style.css` 和 `script.js`，那么 `public/calc/` 下的所有文件都会一起被发布，页面里的相对路径也照常工作。

然后在文章里链接过去就行：

```markdown
我做了个[小工具](/calc/)，可以试试。
```

**这种方式特别适合**：单页 demo、课程作业、数据可视化、小游戏 —— 任何"我自己写好了完整页面"的东西，完全不需要改造成 Astro 组件。

### 情况 3：会重复用到的 HTML，做成组件

如果这段 HTML 你打算在好几篇文章里用（比如一个固定的"关于作者"卡片），别复制粘贴，做成组件。

新建 `src/components/AuthorCard.astro`：

```astro
---
// 组件可以接收参数
const { name = '站长' } = Astro.props;
---
<div class="author-card">
  <img src="/avatar.jpg" alt={name}>
  <div>
    <strong>{name}</strong>
    <p>随便写点什么。</p>
  </div>
</div>
```

然后把文章改成 `.mdx` 后缀（`my-post.mdx`），在开头导入：

```mdx
---
title: 我的文章
date: 2026-09-26
---

import AuthorCard from '../../components/AuthorCard.astro';

正文写在这里。

<AuthorCard name="蓝天白云" />
```

> `.mdx` 和 `.md` 的区别就是：MDX 里可以写组件和 JS 表达式。除了这个能力，其余写法完全一样。前面的 `content.config.ts` 里我已经把 `mdx` 也包含进去了（`pattern: '**/*.{md,mdx}'`）。

### 情况 4：想改站点本身的 HTML 结构

比如想把页脚、侧边栏换成自己的 HTML —— 这叫**组件覆盖**。

以页脚为例，新建 `src/components/Footer.astro`：

```astro
---
const year = new Date().getFullYear();
---
<footer class="site-footer">
  <p>© {year} 我的博客</p>
</footer>
```

然后在 `astro.config.mjs` 里登记：

```js
starlight({
  components: {
    Footer: './src/components/Footer.astro',
  },
});
```

Starlight 会把默认页脚换成你这个。可覆盖的组件不止页脚，还有 `Head`（往 `<head>` 里塞东西）、`Hero`（首页大标题区）、`Sidebar` 等等。

> 这个站点的页脚就是这么改的 —— 加上了许可协议和"源码"链接。

### 小结一下

| 你的 HTML 是… | 放哪 | 怎么用 |
|---|---|---|
| 一小段片段 | 直接写在 `.md` 里 | 注意 HTML 块内的 Markdown 不生效 |
| 完整的一个页面 | `public/` 目录 | 原样发布，用链接或 iframe 引 |
| 会反复用的片段 | 做成 `.astro` 组件 | 在 `.mdx` 里 import |
| 要替换站点自己的部分 | 组件 + `components` 配置 | 覆盖 Starlight 默认组件 |

---

## 十五、我踩过的坑，你可以直接跳过

**Markdown 表格的单元格里不能有换行。** 我迁移旧数据时踩的 —— 表格行里一旦有换行，整张表会退化成一堆竖线文字。手写一般不会遇到，但如果你的内容是从别处自动转过来的，记得检查。

**HTML 块里的 Markdown 不生效。** 上面第十四节详细说了 —— 这个坑最容易让人怀疑人生，因为页面不会报错，只是那几行"看起来怪怪的"。

**Starlight 不会帮你解析相对 `.md` 链接。** 写 `[另一篇](other.md)` 在构建后依然是 `other.md`，点开就 404。要写完整路径 `/blog/other/`。

**无头浏览器截图有最小窗口宽度。** 如果你也用截图来检查排版 —— Windows 上传 `--window-size=430` 实际会按 510px 排版再裁成 430px，看着像"内容被切掉了"，其实页面没毛病。要测手机版得用 iframe 包一层。

**别把构建产物提交进仓库。** 记得在 `.gitignore` 里加上 `dist/` 和 `node_modules/`。

---

## 十六、花了多少钱

**0 元。**

- GitHub 仓库：免费
- GitHub Pages 托管：免费（公开仓库不限流量）
- 构建：GitHub Actions 公开仓库免费
- 字体：开源免费

唯一可能花钱的是自定义域名，一年几十块，不买也完全能用。

---

## 写在最后

这套方案最爽的地方是**内容完全属于你自己**。

它就是你电脑上的一堆 Markdown 文件，同步在你自己 GitHub 账号里。哪天不想用了，复制走就行 —— 不用导出数据库，不用担心平台关停或者涨价。

整个站现在的规模：`301` 个文件、`7.65 MB`、构建一次约 `10 秒`。其中我自己写的代码只有 `188 KB`，剩下的都是依赖和图片。

如果这篇对你有用，或者你搭的时候卡在哪一步，欢迎找我聊。
