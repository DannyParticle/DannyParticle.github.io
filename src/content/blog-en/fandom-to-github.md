---
title: "Moving a Fandom Wiki to GitHub Pages: The Whole Process"
date: 2026-09-20
category: Tinkering Log
excerpt: Exporting, converting, scraping images, and the pitfalls of access from mainland China.
cover: /wiki-images/Screenshot 2025-09-17 120424.webp
---

Fandom is unreachable from mainland China, so the entire wiki was moved to GitHub Pages. Here is how it went.

## 1. Getting the content out

Fandom runs on MediaWiki, so the content can be exported directly as XML. But the XML contains **no images** — those live on a CDN,
so another approach was needed. In the end, every page was saved in the browser with "Save as complete webpage", which brought the images along with it.

## 2. Converting wikitext to Markdown

A converter was written to handle these syntaxes:

- `{{infobox}}` templates → the infobox card on the right
- `{| |}` tables → Markdown or HTML tables
- `[[Page|Text]]` → relative links
- `[[Category:X]]` → front matter tags
- `<gallery>` → responsive image galleries

## 3. The pitfalls

**Image paths were one level short.** MkDocs enables `use_directory_urls` by default, so a page file lives at
`docs/wiki/characters/xxx.md`, while its actual URL is `/wiki/characters/xxx/` — one directory deeper than the file path.
Computing relative paths from the file hierarchy made every image on the site return a 404.

**Markdown does not work inside raw HTML blocks.** The infobox is an HTML table, and writing
`![avatar](path)` inside it simply prints those characters, so real `<img>` tags are required.

**Filenames change when the browser saves them.** Chinese characters become `%3F`, spaces become underscores, PNGs are saved as webp thumbnails,
and duplicate names gain a `(1)` suffix — all of which has to be normalized when matching.
