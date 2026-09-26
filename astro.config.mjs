// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://dannyparticle.github.io',
  integrations: [
    starlight({
      title: '王维诗里的MBTI',
      description:
        'bilibili 频道「王维诗里的MBTI」的资料站：角色档案、作品设定与荣格八维理论。',
      defaultLocale: 'root',
      locales: {
        root: { label: '简体中文', lang: 'zh-CN' },
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/DannyParticle' },
      ],
      customCss: ['./src/styles/custom.css'],
      components: {
        Footer: './src/components/Footer.astro',
      },
      // 自托管的霞鹜文楷（屏幕阅读版）—— 不挂 CDN，大陆访问才稳
      head: [
        {
          tag: 'link',
          attrs: { rel: 'stylesheet', href: '/fonts/wenkai.css' },
        },
      ],
      // 资料站的每一页都带侧边栏；博客是自定义页面，不受这里影响
      sidebar: [
        { label: '博客首页', link: '/' },
        { label: '全部文章', link: '/blog/' },
        {
          label: '资料站',
          items: [
            { label: '维基首页', slug: 'wiki' },
            { label: '关于本维基', slug: 'wiki/about' },
            { label: '频道介绍', slug: 'wiki/channel' },
            {
              label: '角色档案',
              items: [
                { label: '胡紫（INTJ）', slug: 'wiki/characters/huzi-intj' },
                { label: '舒迢（INTP）', slug: 'wiki/characters/shutiao-intp' },
                { label: '吕强人（ENTJ）', slug: 'wiki/characters/lvqiangren-entj' },
                { label: '郭哲梅（ENTP）', slug: 'wiki/characters/guozhemei-entp' },
                { label: '百里透黑（INFJ）', slug: 'wiki/characters/bailitouhei-infj' },
                { label: '萧福叠（INFP）', slug: 'wiki/characters/xiaofudie-infp' },
                { label: '苏达简（ENFJ）', slug: 'wiki/characters/sudajian-enfj' },
                { label: '修勾勾（ENFP）', slug: 'wiki/characters/xiugougou-enfp' },
                { label: '郝瑟（ISTJ）', slug: 'wiki/characters/haose-istj' },
                { label: '马麻（ISFJ）', slug: 'wiki/characters/mama-isfj' },
                { label: '池梓（ESTJ）', slug: 'wiki/characters/chizi-estj' },
                { label: '单歌（ESFJ）', slug: 'wiki/characters/shange-esfj' },
                { label: '祖安（ISTP）', slug: 'wiki/characters/zuan-istp' },
                { label: '柳怜（ISFP）', slug: 'wiki/characters/liulian-isfp' },
                { label: '莫竞（ESTP）', slug: 'wiki/characters/mojing-estp' },
                { label: '崔崔（ESFP）', slug: 'wiki/characters/cuicui-esfp' },
              ],
            },
            {
              label: '设定与作品',
              items: [
                { label: '《不器》', slug: 'wiki/works/buqi' },
                { label: '工作室', slug: 'wiki/studio' },
                { label: '各 MBTI 排列组合', slug: 'wiki/pairings' },
                { label: 'B站二创精选', slug: 'wiki/works/bilibili-fanworks' },
              ],
            },
            { label: '荣格理论和荣格八维', slug: 'wiki/theory/jung-eight-functions' },
            {
              label: '相关人物',
              items: [
                { label: '王元元', slug: 'wiki/people/wangyuanyuan' },
                { label: '维基', slug: 'wiki/people/viki' },
                { label: '云中鹿饮溪', slug: 'wiki/people/yunzhongluyinxi' },
                { label: '狐狸刷刷', slug: 'wiki/people/hulishuashua' },
                { label: '骨哥说', slug: 'wiki/people/guge' },
              ],
            },
          ],
        },
      ],
    }),
  ],
});
