---
title: 把 Fandom 维基搬到 GitHub Pages 的全过程
date: 2026-09-20
category: 折腾记
excerpt: 导出、转换、图片抓取，以及大陆访问的那些坑。
cover: /wiki-images/Screenshot 2025-09-17 120424.webp
---

Fandom 在中国大陆访问不了，于是把维基整个搬到了 GitHub Pages。记一下过程。

## 一、把内容弄出来

Fandom 是 MediaWiki，可以直接导出 XML。但 XML 里**没有图片** —— 图片在 CDN 上，
得另外想办法。最后是把每个页面用浏览器「另存为完整网页」，图片就跟着存下来了。

## 二、wikitext 转 Markdown

写了个转换器处理这些语法：

- `{{信息框}}` 模板 → 右侧信息卡
- `{| |}` 表格 → Markdown 或 HTML 表格
- `[[页面|文字]]` → 相对链接
- `[[分类:X]]` → front matter 标签
- `<gallery>` → 响应式图集

## 三、踩到的坑

**图片路径少一层。** MkDocs 默认 `use_directory_urls`，页面文件是
`docs/wiki/characters/xxx.md`，但实际 URL 是 `/wiki/characters/xxx/` —— 比文件路径多一层目录。
按文件层级算相对路径，全站图片就 404 了。

**Markdown 不会在裸 HTML 块里生效。** 信息卡是一张 HTML 表格，里面写
`![头像](路径)` 会原样显示出来，必须换成真正的 `<img>` 标签。

**浏览器另存的文件名会变形。** 中文变成 `%3F`、空格变成下划线、PNG 存成 webp 缩略图、
重名加 `(1)` 后缀 —— 匹配的时候都要归一化处理。
