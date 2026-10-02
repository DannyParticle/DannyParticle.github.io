// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://dannyparticle.github.io',
  integrations: [
    starlight({
      title: '蓝天白云的小站',
      description:
        '个人博客 —— 随笔、折腾记，以及一个 MBTI 动画频道的资料站。',
      logo: { src: './public/avatar.jpg', alt: '蓝天白云的小站' },
      favicon: '/favicon.png',
      // 多语言：简体中文在根路径，英文在 /en/ 下。
      // Starlight 顶栏会自动出现语言选择器，并且是「按页对应」——
      // 在 /wiki/channel/ 上选 English 会去 /en/wiki/channel/，
      // 那一页没译文时退回该语言的首页。这和 Fandom 的跨语言链接是一个思路。
      defaultLocale: 'root',
      locales: {
        root: { label: '简体中文', lang: 'zh-CN' },
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/DannyParticle' },
        {
          icon: 'external',
          label: 'Bilibili',
          href: 'https://space.bilibili.com/1922582514',
        },
      ],
      customCss: ['./src/styles/custom.css'],
      components: {
        Footer: './src/components/Footer.astro',
        // 覆盖主题选择器 = 顺手在顶栏右侧挂上字体/繁简切换
        ThemeSelect: './src/components/overrides/ThemeSelect.astro',
      },
      // 资料站每页底部给一个「在 GitHub 上编辑」的入口（编辑器挂了还能兜底）
      editLink: {
        baseUrl: 'https://github.com/DannyParticle/DannyParticle.github.io/edit/main/',
      },
      // 字体：四套自托管中文字体，全部完整不分片
      //（分片虽然省流量，但新增内容一旦落在未覆盖区就会掉字体，看起来像缺字）
      head: [
        {
          // 分片字体的 @font-face（霞鹜文楷 / 思源宋体，96 片 × 2）
          tag: 'link',
          attrs: { rel: 'stylesheet', href: '/fonts/sliced.css' },
        },
        {
          // 整包字体（MiSans / HarmonyOS）与 --site-font 变量
          tag: 'link',
          attrs: { rel: 'stylesheet', href: '/fonts/site-fonts.css' },
        },
        {
          // 字体选择必须在首屏渲染前写进 <html>，否则回访用户会先看到默认字体
          // 再「跳」成自己选的那套。和 Starlight 处理暗色模式是同一个套路。
          tag: 'script',
          attrs: { is: 'inline' },
          content:
            "(function(){try{var f=localStorage.getItem('site-font');" +
            "if(f&&['wenkai','misans','harmonyos','noto-serif'].indexOf(f)>=0)" +
            "document.documentElement.dataset.font=f;}catch(e){}})();",
        },
      ],
      // 侧边栏分两块：博客 + 资料站。
      // 资料站设成 collapsed，在博客/首页时收起，点进资料站会自动展开
      //（Starlight 会展开包含当前页面的分组），两边互不干扰。
      sidebar: [
        {
          label: '博客', translations: { en: 'Blog' },
          items: [
            { label: '首页', translations: { en: 'Home' }, link: '/' },
            { label: '全部文章', translations: { en: 'All posts' }, link: '/blog/' },
          ],
        },
        {
          label: '资料站', translations: { en: 'Wiki' },
          collapsed: true,
          items: [
            { label: '维基首页', translations: { en: 'Wiki home' }, slug: 'wiki' },
            { label: '关于本维基', translations: { en: 'About this wiki' }, slug: 'wiki/about' },
            { label: '频道介绍', translations: { en: 'Channel' }, slug: 'wiki/channel' },
            {
              label: '角色档案', translations: { en: 'Characters' },
              items: [
                { label: '胡紫（INTJ）', translations: { en: 'Huzi (INTJ)' }, slug: 'wiki/characters/huzi-intj' },
                { label: '舒迢（INTP）', translations: { en: 'Shutiao (INTP)' }, slug: 'wiki/characters/shutiao-intp' },
                { label: '吕强人（ENTJ）', translations: { en: 'Lü Qiangren (ENTJ)' }, slug: 'wiki/characters/lvqiangren-entj' },
                { label: '郭哲梅（ENTP）', translations: { en: 'Guo Zhemei (ENTP)' }, slug: 'wiki/characters/guozhemei-entp' },
                { label: '百里透黑（INFJ）', translations: { en: 'Bailitouhei (INFJ)' }, slug: 'wiki/characters/bailitouhei-infj' },
                { label: '萧福叠（INFP）', translations: { en: 'Xiaofudie (INFP)' }, slug: 'wiki/characters/xiaofudie-infp' },
                { label: '苏达简（ENFJ）', translations: { en: 'Su Dajian (ENFJ)' }, slug: 'wiki/characters/sudajian-enfj' },
                { label: '修勾勾（ENFP）', translations: { en: 'Xiugougou (ENFP)' }, slug: 'wiki/characters/xiugougou-enfp' },
                { label: '郝瑟（ISTJ）', translations: { en: 'Haose (ISTJ)' }, slug: 'wiki/characters/haose-istj' },
                { label: '马麻（ISFJ）', translations: { en: 'Mama (ISFJ)' }, slug: 'wiki/characters/mama-isfj' },
                { label: '池梓（ESTJ）', translations: { en: 'Chizi (ESTJ)' }, slug: 'wiki/characters/chizi-estj' },
                { label: '单歌（ESFJ）', translations: { en: 'Shange (ESFJ)' }, slug: 'wiki/characters/shange-esfj' },
                { label: '祖安（ISTP）', translations: { en: 'Zuan (ISTP)' }, slug: 'wiki/characters/zuan-istp' },
                { label: '柳怜（ISFP）', translations: { en: 'Liulian (ISFP)' }, slug: 'wiki/characters/liulian-isfp' },
                { label: '莫竞（ESTP）', translations: { en: 'Mojing (ESTP)' }, slug: 'wiki/characters/mojing-estp' },
                { label: '崔崔（ESFP）', translations: { en: 'Cuicui (ESFP)' }, slug: 'wiki/characters/cuicui-esfp' },
              ],
            },
            {
              label: '设定与作品', translations: { en: 'Setting & works' },
              items: [
                { label: '《不器》', translations: { en: 'Buqi' }, slug: 'wiki/works/buqi' },
                { label: '工作室', translations: { en: 'Studio' }, slug: 'wiki/studio' },
                { label: '各 MBTI 排列组合', translations: { en: 'MBTI combinations' }, slug: 'wiki/pairings' },
                { label: 'B站二创精选', translations: { en: 'Fan works showcase' }, slug: 'wiki/works/bilibili-fanworks' },
              ],
            },
            { label: '荣格理论和荣格八维', translations: { en: 'Jungian theory & the eight functions' }, slug: 'wiki/theory/jung-eight-functions' },
            {
              label: '相关人物', translations: { en: 'People' },
              items: [
                { label: '王元元', translations: { en: 'Wang Yuanyuan' }, slug: 'wiki/people/wangyuanyuan' },
                { label: '维基', translations: { en: 'Wiki' }, slug: 'wiki/people/viki' },
                { label: '云中鹿饮溪', translations: { en: 'Yunzhong Luyinxi' }, slug: 'wiki/people/yunzhongluyinxi' },
                { label: '狐狸刷刷', translations: { en: 'Hulishuashua' }, slug: 'wiki/people/hulishuashua' },
                { label: '骨哥说', translations: { en: 'Guge Shuo' }, slug: 'wiki/people/guge' },
              ],
            },
          ],
        },
      ],
    }),
  ],
});
