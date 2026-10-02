---
title: "Build a Blog from Scratch: Astro + GitHub Pages, Step by Step"
date: 2026-09-26
category: Tinkering Log
excerpt: No server, no cost — host your blog on GitHub. From setting up your environment to publishing your first post, every step spelled out.
cover: /covers/build-a-blog.png
---

I had wanted a place of my own to write for a long time. I tried a few blogging platforms, and in the end I decided to build one myself.

This post records the whole process. **It assumes you have never touched any of this before — just follow along.** You won't buy a server or a domain, and the total cost is zero.

The end result is this very site: a homepage, a post list, categories, working search — and publishing an article means dropping in a single file.

---

## 1. How this actually works

A traditional blog (WordPress, say) works like this: the content lives in a **database**, and when a visitor opens a page, the server queries the database, assembles a page, and sends it over. So you have to rent a server, set up the environment, back everything up on a schedule, and defend against attacks.

This approach is completely different:

```
你写 .md 文件  →  提交到 GitHub  →  GitHub 自动编译成 HTML  →  访客看到静态页面
```

**The key difference**: compilation happens exactly once, at the moment you commit, and what it produces is plain HTML files. Nothing is computed when a visitor opens a page — the finished file is simply sent over.

The benefits are concrete:

- No server, and nothing to maintain
- Fast — no database queries
- Cheap — GitHub Pages is free
- The content is your own files, ready to move elsewhere whenever you like

The downsides, to be clear: **no visual admin panel**, **comments need a third-party service**, and **builds get slower as content grows** (irrelevant below a few thousand posts).

---

## 2. What you need

Three things:

1. **A GitHub account** — free to register
2. **Node.js** — download the LTS build from the official site and click Next through the installer; if typing `node -v` in a terminal shows a version number, you're set
3. **Something to edit text with** — VS Code is the nicest option, though Notepad will do

That's all. No domain to buy (GitHub gives you a `你的用户名.github.io` for free), and no server.

---

## 3. Creating the project

Open a terminal (PowerShell on Windows), go to the directory where you keep your code, and run:

```bash
npm create astro@latest my-blog -- --template starlight
```

That line downloads the Astro project template for you. It will ask you a few questions along the way; just take the defaults (press Enter).

`--template starlight` means "use the Starlight theme" — Astro's official documentation theme, which comes with a sidebar and search built in. It makes a very good foundation for a blog.

Then go in and install the dependencies:

```bash
cd my-blog
npm install
```

> If the network is slow in mainland China, add a mirror: `npm install --registry=https://registry.npmmirror.com`

When that finishes, start it up and take a look:

```bash
npm run dev
```

The terminal prints an address (usually `http://localhost:4321`). Open it in a browser; if you see a default page, your environment is working.

---

## 4. Making it your own

Open `astro.config.mjs`, the configuration file for the whole site. Start by changing these to your own values:

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

The `site` field **must be correct**, because it determines the links and the sitemap generated later.

---

## 5. Writing your first post

Create a new file under `src/content/blog/`, for example `hello.md`:

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

Save it. That's all there is to it — **dropping the file in counts as publishing**; there is no "publish" action to perform.

Those opening lines (the part wrapped in `---`) are called **frontmatter**, and they are the post's metadata:

| Field | Purpose | Required |
|---|---|---|
| `title` | Post title | ✅ |
| `date` | Date, determines the ordering | ✅ |
| `category` | Category, used for grouping | Optional; defaults to "随笔" |
| `excerpt` | Summary, shown in lists and on homepage cards | Optional |
| `cover` | Path to the cover image | Optional |
| `draft` | Set to `true` and it won't be published | Optional |

These fields aren't arbitrary; you have to declare them in the config first (covered in the next section).

---

## 6. Teaching Astro about your posts

Open `src/content.config.ts` and add this block:

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

This is the "declaration" for the fields in the table above. It's how Astro knows that the files in `src/content/blog/` are posts, and it will **check them for you**: a missing title or a badly formatted date makes the build fail with an error instead of quietly rendering a blank page.

> This is called a content collection. `z` is the data validation library zod: `z.string()` means "must be text", `.optional()` means "may be omitted", and `.default('随笔')` means "use this value when it is omitted".

---

## 7. Three pages are enough for the whole blog

Now you have posts, but no pages to display them. A blog really only needs three pages:

### 1. The post list page

Create `src/pages/blog/index.astro`:

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

Two key lines, explained:

- `getCollection('blog', ...)` — reads every post in `src/content/blog/` and filters out drafts
- `.sort(...)` — sorts by date in descending order, newest first

### 2. The post detail page

Create `src/pages/blog/[...slug].astro`:

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

The `[...slug]` in the filename is a **wildcard route**: `hello.md` automatically becomes `/blog/hello/`, and `foo.md` becomes `/blog/foo/`.

`getStaticPaths()` exists so that "however many posts you have, that's how many HTML pages get built". **This is why adding a file is all it takes to publish** — there is nothing to register by hand.

`<Content />` renders the Markdown body as HTML.

### 3. Latest posts on the homepage

The homepage doesn't need its own list; pull it out into a component, `src/components/LatestPosts.astro`:

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

Notice that this is the **same query** as the list page, with nothing added but a `.slice(0, 3)`. So once you publish a new post, **the homepage updates itself** — nothing to edit by hand.

Then drop it into the homepage (`src/content/docs/index.mdx`):

```mdx
import LatestPosts from '../../components/LatestPosts.astro';

<LatestPosts />
```

---

## 8. Tweaking the look

Styles live in `src/styles/custom.css`, registered through `astro.config.mjs`:

```js
starlight({
  customCss: ['./src/styles/custom.css'],
});
```

A few adjustments with the biggest visual impact:

**① Change the accent color.** Starlight controls its palette with CSS variables, so you just override them:

```css
:root {
  --sl-color-accent-low: #ece8f9;
  --sl-color-accent: #6d5bd0;      /* 主色 */
  --sl-color-accent-high: #3a2d78;
}
```

**② Typesetting for Chinese.** The default typography is tuned for English, which leaves Chinese text looking cramped:

```css
:root {
  --sl-text-base: 1.02rem;   /* 字号大一点 */
  --sl-line-height: 1.85;    /* 行距松一点 */
}

.sl-markdown-content p {
  margin-block: 1.1em;       /* 段间距 */
}
```

**③ Cards, rounded corners, shadows.** These are purely a matter of taste, and keeping them in shared variables makes them easy to adjust site-wide:

```css
:root {
  --site-radius: 12px;
  --site-shadow: 0 1px 2px #1a1a2e0a, 0 4px 14px #1a1a2e0d;
}
```

---

## 9. Switching to a nicer Chinese font (optional, but worth it)

The system's built-in sans-serif gets bland after a while. I use **LXGW WenKai** (霞鹜文楷) — open source and free, with the feel of a regular script, and a great fit for a Chinese blog.

**Pitfall one: the font files are huge.** The full set is 4.87 MB, and making visitors download all of it before they can read is unacceptable.

**The fix is `unicode-range` slicing.** LXGW WenKai has a ready-made npm package that has already split the font into 97 small files, each holding only a subset of the Chinese characters:

```bash
npm install lxgw-wenkai-screen-webfont
```

Copy that package's `css` and `files/` directory into `public/fonts/`, then pull it in from the config:

```js
starlight({
  head: [
    { tag: 'link', attrs: { rel: 'stylesheet', href: '/fonts/site-fonts.css' } },
  ],
});
```

Based on the characters that actually appear on the page, the browser **downloads only the slices it needs** (about 7 KB each). A Chinese blog typically loads a dozen or so slices above the fold — under 100 KB, entirely acceptable.

Finally, use it in your CSS:

```css
:root {
  --sl-font: "LXGW WenKai Screen", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}
```

> **Pitfall two**: LXGW WenKai has **only one weight (400)**. If you set `font-weight: 700` on headings, the browser will "synthesize" a fake bold, and synthetic bold on a regular script tends to look smudged. Setting headings to `600`, or simply using size and color to establish hierarchy, looks better.
>
> **Pitfall three**: don't host the font on a CDN like jsDelivr. Access from mainland China is unreliable, and the font is a first-paint resource — if it fails to load, you get a large blank area. Self-hosting is the safest option.

---

## 10. Search comes free

Starlight bundles Pagefind search. **There is nothing to configure** — the build scans every page and generates an index automatically, and the search box in the top right just works (`Ctrl + K`).

Search runs entirely in the browser, so no search service is required.

---

## 11. Deploying to GitHub Pages

This is the last step, and the one people get stuck on most.

### 1. Create a repository and push

Create a new repository on GitHub. **The name matters**:

- If you want the address to be `https://你的用户名.github.io`, the repository must be named `你的用户名.github.io`
- Any other name works too, but the address becomes `https://你的用户名.github.io/仓库名/`

Once it's created, run this inside your local project:

```bash
git init -b main
git add -A
git commit -m "第一版"
git remote add origin git@github.com:你的用户名/仓库名.git
git push -u origin main
```

> SSH (`git@github.com:...`) is more reliable than HTTPS, and noticeably so on mainland Chinese networks. The first time around, you'll need to add an SSH public key in your GitHub settings.

### 2. Add an automated build workflow

Create `.github/workflows/deploy.yml` in the project with this content:

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

What this means: **every time you push to the `main` branch, GitHub runs a build on its own servers and publishes the result.** You don't have to do anything, and you don't need to build locally.

A few things that trip people up:

- Those three lines under `permissions` **cannot be omitted**, or the workflow has no permission to publish
- I deliberately used `npm install` instead of `npm ci` — some packages (sharp, for instance) ship platform-specific binaries, and since your machine is Windows while the build runner is Linux, `ci` can fail outright on a lockfile mismatch
- `path: dist` has to match Astro's output directory (which is `dist` by default)

### 3. Turn on Pages

After pushing, go to the repository's **Settings → Pages** and change **Source to `GitHub Actions`**.

Then go back to the repository's **Actions** tab, where you should see a job in progress. A green check means it worked — visit `https://你的用户名.github.io` and your blog will be there.

From then on, every push triggers a rebuild automatically, live in about a minute.

---

## 12. Binding your own domain (optional)

If you'd rather not use `github.io`:

1. Buy a domain and add a `CNAME` record in DNS pointing to `你的用户名.github.io`
2. Enter your domain under Settings → Pages → Custom domain in the repository
3. Check `Enforce HTTPS`

**But GitHub Pages itself is not very stable from mainland China.** If you want more speed, the usual move is to host your domain's DNS on Cloudflare for an extra layer of acceleration. There are plenty of pitfalls here; I'll write about it separately another day.

---

## 13. Publishing posts day to day

Once everything is set up, publishing takes three steps:

**① Create a file** — `src/content/blog/文章名.md`

**② Fill in the opening lines**:

```markdown
---
title: 文章标题
date: 2026-09-26
category: 随笔
excerpt: 一句话摘要
---
```

**③ Push**:

```bash
git add -A
git commit -m "新文章"
git push
```

Wait a minute and it's live. The list, the categories, the homepage, the search index, and the sitemap **all update automatically**.

---

## 14. I already have HTML — how do I put it in?

This comes up often: you wrote a small tool, built a page, or copied a chunk of HTML from somewhere and want to use it. Four cases, one at a time.

### Case 1: a snippet of HTML to insert in the middle of a post

Markdown **supports raw HTML to begin with**, so just paste it into the post:

```markdown
这是普通段落。

<div style="padding: 12px; border-left: 3px solid #6d5bd0; background: #f6f5fb;">
  这是一个自己写的提示框。
</div>

这又是普通段落。
```

**⚠️ But there's a big pitfall here**: Markdown **inside an HTML block does not work**.

```markdown
<div class="tip">
这段 **不会**变粗 —— 会原样显示两个星号。
</div>

这段 **会**变粗 —— 因为空行让它回到了 Markdown 语境。
```

The reason is that once the Markdown parser sees `<div>`, it treats the whole block as raw source and outputs it verbatim, no longer parsing the syntax inside. I hit this one hard when I was building the wiki's infobox cards — every image and link in those cards showed up as source code.

**Two ways around it:**

**Option A: inside HTML blocks, use plain HTML and don't mix in Markdown**

```markdown
<div class="tip">
  <strong>加粗</strong>、<a href="/blog/">链接</a>、<img src="/covers/x.png" alt="">
</div>
```

**Option B: if you do mix them, put each element on its own line**

```markdown
<div class="tip">

这里可以写 **Markdown**，因为前后都有空行。

</div>
```

> Any CSS class names you use have to be defined yourself in `src/styles/custom.css`; the HTML only provides the structure.

### Case 2: a complete HTML page (a tool, demo, or game you wrote)

This one is the easiest — **just drop the file into the `public/` directory**.

Anything in `public/` is **copied verbatim** to the site root, with no processing at all. So:

```
public/demo/index.html   →  访问 https://你的域名/demo/
public/tool.html         →  访问 https://你的域名/tool.html
```

Say you wrote a single-file calculator at `public/calc/index.html` that references `style.css` and `script.js` in the same directory — then every file under `public/calc/` is published along with it, and the relative paths inside the page keep working.

Then just link to it from a post:

```markdown
我做了个[小工具](/calc/)，可以试试。
```

**This approach is especially good for**: single-page demos, coursework, data visualizations, small games — anything where "I already have a complete page of my own". There is no need to convert it into an Astro component at all.

### Case 3: HTML you'll reuse — make it a component

If you plan to use a piece of HTML across several posts (a fixed "about the author" card, say), don't copy and paste it — make it a component.

Create `src/components/AuthorCard.astro`:

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

Then rename the post with an `.mdx` extension (`my-post.mdx`) and import it at the top:

```mdx
---
title: 我的文章
date: 2026-09-26
---

import AuthorCard from '../../components/AuthorCard.astro';

正文写在这里。

<AuthorCard name="蓝天白云" />
```

> The only difference between `.mdx` and `.md` is that MDX lets you write components and JS expressions. Apart from that ability, everything else is written in exactly the same way. In the `content.config.ts` above I already included `mdx` (`pattern: '**/*.{md,mdx}'`).

### Case 4: changing the site's own HTML structure

Say you want to replace the footer or the sidebar with your own HTML — this is called **component overriding**.

Taking the footer as an example, create `src/components/Footer.astro`:

```astro
---
const year = new Date().getFullYear();
---
<footer class="site-footer">
  <p>© {year} 我的博客</p>
</footer>
```

Then register it in `astro.config.mjs`:

```js
starlight({
  components: {
    Footer: './src/components/Footer.astro',
  },
});
```

Starlight swaps its default footer for yours. The footer isn't the only component you can override; there's also `Head` (for injecting things into `<head>`), `Hero` (the big title area on the homepage), `Sidebar`, and more.

> That is exactly how this site's footer was customized — a license and a "source" link were added.

### Summary

| What your HTML is… | Where it goes | How to use it |
|---|---|---|
| A short snippet | Written directly in the `.md` file | Note that Markdown inside HTML blocks won't work |
| A complete page | The `public/` directory | Published as-is; reference it with a link or an iframe |
| A snippet you'll reuse | Make it an `.astro` component | Import it in an `.mdx` file |
| A part of the site itself you want to replace | A component plus the `components` config | Override Starlight's default component |

---

## 15. Pitfalls I hit, so you can skip them

**Markdown table cells cannot contain line breaks.** I ran into this while migrating old data — one line break inside a table row and the whole table degrades into a pile of pipe characters. Hand-written tables rarely hit this, but if your content was converted automatically from somewhere else, check it.

**Markdown inside HTML blocks doesn't work.** Section 14 above covers this in detail — it's the pitfall most likely to make you question everything, because nothing errors out; those few lines just "look odd".

**Starlight won't resolve relative `.md` links for you.** Write `[另一篇](other.md)` and it is still `other.md` after the build, so clicking it gives a 404. Use the full path, `/blog/other/`.

**Headless browser screenshots have a minimum window width.** If you also check layout with screenshots — on Windows, passing `--window-size=430` actually lays out at 510px and then crops to 430px, which looks like "the content is cut off" even though the page is fine. To test the mobile version you have to wrap it in an iframe.

**Don't commit build output to the repository.** Remember to add `dist/` and `node_modules/` to `.gitignore`.

---

## 16. What it cost

**Zero.**

- GitHub repository: free
- GitHub Pages hosting: free (unlimited traffic for public repositories)
- Builds: GitHub Actions is free for public repositories
- Font: open source and free

The only thing that might cost money is a custom domain — a few tens of yuan a year — and you can skip it entirely and still be perfectly fine.

---

## Final thoughts

The best part of this setup is that **the content belongs entirely to you**.

It's just a pile of Markdown files on your computer, synced to your own GitHub account. If you ever want out, copy them and go — no database export, no worrying about a platform shutting down or raising its prices.

The site's current size: `301` files, `7.65 MB`, and about `10 seconds` per build. Of that, only `188 KB` is code I wrote myself; the rest is dependencies and images.

If this was useful, or if you get stuck on a step while building yours, feel free to reach out.
