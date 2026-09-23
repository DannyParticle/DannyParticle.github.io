/* ============================================================================
 * 王维诗里的MBTI Wiki —— 浏览器端一键存档
 * ----------------------------------------------------------------------------
 * 用途：当这台电脑没有全局代理、只有浏览器能访问 Fandom 时，用浏览器自己把
 *       整个维基（所有页面 HTML + wikitext + 全部图片）打包成一个 zip 下载。
 *
 * 用法：
 *   1. 用浏览器打开维基任意页面（确保能正常访问、Cloudflare 已通过）
 *      https://wangweishilidembti.fandom.com/zh/wiki/王维诗里的MBTI_Wiki
 *   2. 按 F12 打开开发者工具 → Console（控制台）
 *   3. 把本文件全部内容粘贴进去，回车
 *   4. 等待进度跑完，浏览器会下载 fandom-archive.zip
 *   5. 把这个 zip 放到工作区，告诉我，我来解包、接进站点
 *
 * 说明：脚本用的是同源 API（和页面同一个域名），Cookie 与 Cloudflare 通行证
 *       浏览器会自动带上，所以不会被拦。全程在本机浏览器里跑，不经过第三方。
 * ========================================================================== */
(async () => {
  'use strict';

  const BASE = location.origin;
  const DELAY = 120;          // 每次请求之间的间隔（毫秒），别调太小
  const ZIP_NAME = 'fandom-archive.zip';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // ---------- 1. 找到可用的 api.php ----------
  async function pickApi() {
    const candidates = [];
    const m = location.pathname.match(/^(\/[a-z-]{2,3}(?:-[a-z]{2,4})?)\//);
    if (m) candidates.push(m[1]);
    candidates.push('');
    for (const prefix of candidates) {
      try {
        const r = await fetch(`${BASE}${prefix}/api.php?action=query&meta=siteinfo&siprop=general&format=json`, { credentials: 'include' });
        const j = await r.json();
        if (j.query) { console.log(`[api] 使用 ${prefix}/api.php`); return `${BASE}${prefix}/api.php`; }
      } catch (e) { /* 试下一个 */ }
    }
    throw new Error('找不到可用的 api.php —— 请确认页面能正常打开');
  }

  const API = await pickApi();
  const call = async (params) => {
    const url = `${API}?${new URLSearchParams({ ...params, format: 'json', formatversion: '2' })}`;
    await sleep(DELAY);
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error(`HTTP ${r.status} @ ${url}`);
    return r.json();
  };

  // ---------- 2. zip 写入器（store 模式，不压缩） ----------
  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(u8) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < u8.length; i++) c = (c >>> 8) ^ CRC_TABLE[(c ^ u8[i]) & 0xFF];
    return (c ^ 0xFFFFFFFF) >>> 0;
  }
  function dosDateTime(d = new Date()) {
    const time = ((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() / 2)) & 0xFFFF;
    const date = (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF;
    return { time, date };
  }

  const zip = { parts: [], central: [], offset: 0 };
  const enc = new TextEncoder();

  function addFile(name, data /* Uint8Array */) {
    const nameBytes = enc.encode(name);
    const crc = crc32(data);
    const { time, date } = dosDateTime();
    const local = new Uint8Array(30 + nameBytes.length);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true);
    lv.setUint16(6, 0x0800, true);       // 文件名用 UTF-8
    lv.setUint16(8, 0, true);            // store
    lv.setUint16(10, time, true);
    lv.setUint16(12, date, true);
    lv.setUint32(14, crc, true);
    lv.setUint32(18, data.length, true);
    lv.setUint32(22, data.length, true);
    lv.setUint16(26, nameBytes.length, true);
    lv.setUint16(28, 0, true);
    local.set(nameBytes, 30);

    zip.parts.push(local, data);

    const cd = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(cd.buffer);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(4, 20, true);
    cv.setUint16(6, 20, true);
    cv.setUint16(8, 0x0800, true);
    cv.setUint16(10, 0, true);
    cv.setUint16(12, time, true);
    cv.setUint16(14, date, true);
    cv.setUint32(16, crc, true);
    cv.setUint32(20, data.length, true);
    cv.setUint32(24, data.length, true);
    cv.setUint16(28, nameBytes.length, true);
    cv.setUint32(42, zip.offset, true);
    cd.set(nameBytes, 46);
    zip.central.push(cd);

    zip.offset += local.length + data.length;
  }

  function buildZip() {
    const cdSize = zip.central.reduce((n, c) => n + c.length, 0);
    const eocd = new Uint8Array(22);
    const ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(8, zip.central.length, true);
    ev.setUint16(10, zip.central.length, true);
    ev.setUint32(12, cdSize, true);
    ev.setUint32(16, zip.offset, true);
    return new Blob([...zip.parts, ...zip.central, eocd], { type: 'application/zip' });
  }

  function save(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 5000);
  }

  const safe = (s) => s.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').slice(0, 120);
  const NS_DIR = { 0: 'main', 2: 'user', 4: 'project', 6: 'file', 8: 'mediawiki', 10: 'template', 12: 'help', 14: 'category', 828: 'module', 502: 'user-blog' };

  // ---------- 3. 站点信息 ----------
  const si = await call({ action: 'query', meta: 'siteinfo', siprop: 'general|namespaces|statistics' });
  const general = si.query.general;
  console.log(`%c[站点] ${general.sitename}`, 'font-weight:bold');
  addFile('meta/siteinfo.json', enc.encode(JSON.stringify(si, null, 2)));

  // ---------- 4. 页面清单 ----------
  const namespaces = Object.keys(si.query.namespaces).filter((k) => Number(k) >= 0);
  const pages = [];
  for (const ns of namespaces) {
    let cont = {};
    do {
      const j = await call({ action: 'query', list: 'allpages', apnamespace: ns, aplimit: '500', ...cont });
      (j.query.allpages || []).forEach((p) => pages.push({ ns: p.ns, title: p.title }));
      cont = j.continue || null;
    } while (cont);
  }
  addFile('meta/pages.json', enc.encode(JSON.stringify(pages, null, 2)));
  console.log(`[页面] 共 ${pages.length} 个，开始抓取…`);

  // ---------- 5. 每页：渲染 HTML + wikitext ----------
  const wrapper = (title, body) => `<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>${title.replace(/[<>&]/g, '')}</title>
<style>body{max-width:52rem;margin:2rem auto;padding:0 1rem;line-height:1.75;font-family:system-ui,"Microsoft YaHei",sans-serif}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow-x:auto}th,td{border:1px solid #8884;padding:.35rem .6rem}th{background:#8882}</style>
</head><body><h1>${title}</h1>${body}</body></html>`;

  let done = 0;
  for (const p of pages) {
    const dir = NS_DIR[p.ns] || `ns${p.ns}`;
    const stem = safe(p.title.includes(':') && p.ns !== 0 ? p.title.split(':').slice(1).join(':') : p.title);
    try {
      const parsed = await call({ action: 'parse', page: p.title, prop: 'text|displaytitle', redirects: '1' });
      const body = parsed.parse.text;
      const title = parsed.parse.displaytitle.replace(/<[^>]+>/g, '');
      addFile(`pages/${dir}/${stem}.html`, enc.encode(wrapper(title, body)));
    } catch (e) { console.warn(`  ! HTML 失败 ${p.title}: ${e.message}`); }
    try {
      const rev = await call({ action: 'query', prop: 'revisions', rvprop: 'content', rvslots: 'main', titles: p.title });
      const pg = rev.query.pages[0];
      const content = pg.revisions?.[0]?.slots?.main?.content ?? '';
      addFile(`wikitext/${dir}/${stem}.wiki`, enc.encode(content));
    } catch (e) { console.warn(`  ! wikitext 失败 ${p.title}: ${e.message}`); }
    if (++done % 20 === 0) console.log(`  … ${done}/${pages.length}`);
  }

  // ---------- 6. 图片 ----------
  const images = [];
  let cont = {};
  do {
    const j = await call({ action: 'query', generator: 'allimages', gailimit: '50', prop: 'imageinfo', iiprop: 'url|size|mime|sha1', ...cont });
    (j.query.pages || []).forEach((pg) => {
      const info = (pg.imageinfo || [])[0];
      if (info?.url) images.push({ name: pg.title.replace(/^File:/, ''), url: info.url, size: info.size, mime: info.mime, sha1: info.sha1 });
    });
    cont = j.continue || null;
  } while (cont);

  addFile('meta/images.json', enc.encode(JSON.stringify(images, null, 2)));
  console.log(`[图片] 共 ${images.length} 个，开始下载…`);

  let imgOk = 0, imgFail = 0;
  for (const [i, img] of images.entries()) {
    try {
      await sleep(DELAY);
      const r = await fetch(img.url, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      addFile(`images/${safe(img.name)}`, new Uint8Array(await r.arrayBuffer()));
      imgOk++;
    } catch (e) {
      imgFail++;
      console.warn(`  ! 图片失败 ${img.name}: ${e.message}`);
    }
    if ((i + 1) % 20 === 0) console.log(`  … ${i + 1}/${images.length}（成功 ${imgOk}，失败 ${imgFail}）`);
  }

  // ---------- 7. 索引 + 打包 ----------
  addFile('index.html', enc.encode(`<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>${general.sitename} — 离线存档</title></head><body>
<h1>${general.sitename}</h1>
<p>来源：${general.base || BASE}　页面 ${pages.length}　图片 ${images.length}</p>
<ul>${pages.map((p) => `<li>${p.title}</li>`).join('')}</ul>
</body></html>`));

  console.log('%c[打包] 正在生成 zip…', 'font-weight:bold');
  const blob = buildZip();
  console.log(`[完成] ${(blob.size / 1048576).toFixed(1)} MB —— 开始下载 ${ZIP_NAME}`);
  save(blob, ZIP_NAME);
  console.log('%c[完成] 把下载到的 zip 放进工作区，然后告诉 AI 即可。', 'color:green;font-weight:bold');
})().catch((e) => console.error('存档失败：', e));
