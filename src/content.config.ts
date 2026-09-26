import { defineCollection, z } from 'astro:content';
import { docsLoader, i18nLoader } from '@astrojs/starlight/loaders';
import { docsSchema, i18nSchema } from '@astrojs/starlight/schema';
import { glob } from 'astro/loaders';

export const collections = {
  // 资料站：Starlight 的文档集合，src/content/docs/wiki/* → /wiki/*
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),

  // 界面文案本地化覆盖（这个集合不存在时 Starlight 会告警）
  i18n: defineCollection({ loader: i18nLoader(), schema: i18nSchema() }),

  // 博客：普通内容集合，src/content/blog/*.md → 由 src/pages/blog/ 渲染
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
