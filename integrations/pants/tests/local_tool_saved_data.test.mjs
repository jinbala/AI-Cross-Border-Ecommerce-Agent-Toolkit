import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

function savedData() {
  return {
    meta: {
      source_type: 'product_ranking', is_demo: false, observed_identity: '测试店铺',
      ranking_date: '2026-10-12', period: '近7天（2026-10-06—2026-10-12）',
      collection_scope: '测试首页样本，非全量', generated_at: '2026-10-13T00:00:00Z',
    },
    products: ['女款', '男款'].map((gender, i) => ({
      ranking_date: '2026-10-12', category_path: ['服饰内衣', '服装', i ? '男装' : '女装', '休闲裤'], rank: i + 1,
      product: { id: `test-${i}`, name: `已保存的${gender}裤子`, price_min: null, apparel: { gender, type: '休闲裤' } },
    })),
  };
}

function withTool(contents, check, options = {}) {
  const directory = mkdtempSync(join(tmpdir(), 'pants-saved-'));
  try {
    const dataPath = join(directory, 'saved.json');
    if (contents !== undefined) writeFileSync(dataPath, typeof contents === 'string' ? contents : JSON.stringify(contents), 'utf8');
    const build = spawnSync(process.execPath, ['scripts/build_local_tool.mjs', '--data', dataPath, '--output-dir', directory], { cwd: new URL('..', import.meta.url), encoding: 'utf8' });
    assert.equal(build.status, 0, build.stderr);
    const html = readFileSync(join(directory, 'pants-tool.html'), 'utf8');
    const elements = new Map();
    const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
    const el = id => {
      assert.ok(ids.has(id), 'HTML must contain control '+id);
      if (!elements.has(id)) elements.set(id, {
        _value: '', get value() { return this._value; }, set value(value) { this._value = String(value); },
        checked: false, disabled: false, textContent: '', srcdoc: '', listeners: {},
        addEventListener(type, fn) { this.listeners[type] = fn; },
        setAttribute(name, value) { this[name] = String(value); },
        removeAttribute(name) { this[name] = ''; },
      });
      return elements.get(id);
    };
    const storage = options.storage || new Map(), downloads = [];
    class DownloadURL extends URL {
      static createObjectURL(blob) { downloads.push({ blob }); return 'blob:test'; }
      static revokeObjectURL() {}
    }
    el('update-text').textContent = html.match(/<blockquote id="update-text">([^<]+)<\/blockquote>/)[1];
    const context = vm.createContext({ PANTS_DESKTOP: options.desktop === true, chrome: options.chrome, document: { getElementById: el, createElement: () => ({ click() { downloads.at(-1).name = this.download; } }) }, structuredClone, Blob, URL: DownloadURL, localStorage: options.localStorage || { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) }, navigator: options.navigator || {}, setTimeout: fn => fn(), console });
    new vm.Script(html.match(/<script>([\s\S]*)<\/script>/)[1]).runInContext(context);
    return check({ el, html, storage, downloads, context });
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test('desktop paginates large rankings, searches all rows and exports the entire filtered view', async () => {
  const data=savedData(), template=data.products[0];
  data.products=Array.from({length:205},(_,i)=>({...structuredClone(template),rank:i+1,product:{...structuredClone(template.product),id:'bulk-'+i,name:'测试款-'+i}}));
  await withTool(data,async({el,downloads})=>{
    assert.equal(el('preview').srcdoc,'');
    assert.equal((el('cards').innerHTML.match(/class="product-card"/g)||[]).length,80);
    assert.equal(el('card-pages').hidden,false);
    assert.match(el('card-page-label').textContent,/1 \/ 3/);
    el('card-next').listeners.click();assert.match(el('cards').innerHTML,/测试款-80</);
    el('download').listeners.click();
    const exported=await downloads.at(-1).blob.text();
    assert.match(exported,/测试款-0</);assert.match(exported,/测试款-204</);
    el('query').value='测试款-204';el('query').listeners.input();
    assert.match(el('cards').innerHTML,/测试款-204</);
    assert.equal((el('cards').innerHTML.match(/class="product-card"/g)||[]).length,1);
    assert.equal(el('card-pages').hidden,true);
    el('download').listeners.click();
    const filtered=await downloads.at(-1).blob.text();
    assert.match(filtered,/测试款-204</);assert.doesNotMatch(filtered,/测试款-0</);
  },{desktop:true,chrome:{webview:{postMessage(){}}}});
});

test('saved ranking renders on opening without file import and keeps its actual period', () => {
  withTool(savedData(), ({ el, html }) => {
    assert.equal(el('saved').disabled, false);
    assert.equal(el('download').disabled, false);
    assert.match(el('preview').srcdoc, /已保存的女款裤子/);
    assert.match(el('preview').srcdoc, /已保存的男款裤子/);
    assert.match(el('source').textContent, /测试店铺.*2026-10-06—2026-10-12.*2 条/);
    assert.equal(el('date').value, '2026-10-12');
    assert.match(el('saved-scope').textContent, /非全量.*不会自动刷新罗盘/);
    assert.match(html, /<details><summary>其他数据来源与手工导入（可选）/);
    assert.doesNotMatch(html, /① 下载模板填写数据/);
    el('gender').value = '女款'; el('gender').listeners.input();
    assert.equal(el('download').disabled, false);
    assert.match(el('preview').srcdoc, /已保存的女款裤子/);
    assert.doesNotMatch(el('preview').srcdoc, /已保存的男款裤子/);
    el('demo').listeners.click();
    assert.match(el('source').textContent, /虚构/);
    el('saved').listeners.click();
    assert.match(el('source').textContent, /已保存的真实榜单/);
    assert.match(el('preview').srcdoc, /已保存的女款裤子/);
  });
});

test('quick gender, search and clearing update cards and downloads immediately', () => {
  withTool(savedData(), ({ el }) => {
    el('women').listeners.click();
    assert.equal(el('women')['aria-pressed'], 'true');
    assert.match(el('cards').innerHTML, /已保存的女款裤子/);
    assert.doesNotMatch(el('cards').innerHTML, /已保存的男款裤子/);
    el('query').value = '找不到的款'; el('query').listeners.input();
    assert.equal(el('cards').innerHTML, '');
    assert.equal(el('empty').hidden, false);
    assert.equal(el('download').disabled, true);
    el('empty-reset').listeners.click();
    assert.match(el('cards').innerHTML, /已保存的男款裤子/);
    assert.equal(el('download').disabled, false);
  });
});

test('apply button and native change events filter price bands with missing SKU minimums', () => {
  const data = savedData();
  data.products[0].product.price_band_display = '价格带 ¥99–¥119';
  data.products[0].product.apparel.type = '牛仔裤';
  data.products[1].product.price_band_display = '价格带 ¥379';
  withTool(data, ({ el }) => {
    assert.equal(el('price-basis').value, 'price_band');
    el('floor').value = '100'; el('ceiling').value = '200';
    el('generate').listeners.click();
    assert.match(el('cards').innerHTML, /已保存的女款裤子/);
    assert.doesNotMatch(el('cards').innerHTML, /已保存的男款裤子/);
    assert.match(el('price-feedback').textContent, /有交集/);
    el('ceiling').value = '1000'; el('ceiling').listeners.change();
    assert.match(el('cards').innerHTML, /已保存的男款裤子/);
    el('type').value = '牛仔裤'; el('type').listeners.change();
    el('men').listeners.click();
    assert.equal(el('type').value, '牛仔裤');
    assert.equal(el('empty').hidden, false);
    el('reset').listeners.click();
    assert.match(el('cards').innerHTML, /已保存的女款裤子/);
    assert.match(el('cards').innerHTML, /已保存的男款裤子/);
    el('price-basis').value = 'sku_min'; el('price-basis').listeners.change();
    assert.match(el('price-feedback').textContent, /2 件价格无法判定/);
  });
});

test('favorites survive reopening and stay scoped to the source account', () => {
  const storage = new Map();
  withTool(savedData(), ({ el }) => {
    el('cards').listeners.click({ target: { closest: () => ({ dataset: { favorite: 'test-0' } }) } });
    assert.match(el('favorite-note').textContent, /已保存/);
    el('only-favorites').checked = true; el('only-favorites').listeners.input();
    assert.match(el('cards').innerHTML, /已保存的女款裤子/);
    assert.doesNotMatch(el('cards').innerHTML, /已保存的男款裤子/);
  }, { storage });
  withTool(savedData(), ({ el }) => {
    el('only-favorites').checked = true; el('only-favorites').listeners.input();
    assert.match(el('cards').innerHTML, /已保存的女款裤子/);
    el('cards').listeners.click({ target: { closest: () => ({ dataset: { favorite: 'test-0' } }) } });
    assert.equal(el('empty').hidden, false);
  }, { storage });
  storage.set('pants-favorites-v1:real:测试店铺', '["test-0"]');
  const other = savedData(); other.meta.observed_identity = '其他店铺';
  withTool(other, ({ el }) => {
    el('only-favorites').checked = true; el('only-favorites').listeners.input();
    assert.equal(el('cards').innerHTML, '');
  }, { storage });
});

test('HTML and CSV exports match the current list, preserve unknown price and escape spreadsheet formulas', async () => {
  const data = savedData(); data.products[0].product.name = '=测试女裤';
  const downloads = withTool(data, ({ el, downloads }) => {
    el('women').listeners.click();
    el('download').listeners.click(); el('csv-download').listeners.click();
    return downloads;
  });
  const html = await downloads[0].blob.text(), csv = await downloads[1].blob.text();
  assert.match(html, /=测试女裤/);
  assert.doesNotMatch(html, /已保存的男款裤子/);
  assert.match(csv, /"'=测试女裤"/);
  assert.doesNotMatch(csv, /已保存的男款裤子/);
  assert.match(csv, /"test-0"/);
  assert.match(csv, /"已核实最低价"/);
  assert.ok(downloads[1].name.endsWith('.csv'));
});

test('unavailable browser storage leaves a usable list and explicit unsaved-favorite feedback', () => {
  withTool(savedData(), ({ el }) => {
    el('cards').listeners.click({ target: { closest: () => ({ dataset: { favorite: 'test-0' } }) } });
    assert.match(el('favorite-note').textContent, /仅在本次页面有效/);
    assert.match(el('cards').innerHTML, /★ 已收藏/);
  }, { localStorage: { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } } });
});

test('update instruction copies when available and stays selectable on clipboard failure', async () => {
  let text = '';
  await withTool(savedData(), async ({ el }) => {
    await el('update-copy').listeners.click();
    assert.equal(el('update-instruction').hidden, false);
    assert.match(el('copy-status').textContent, /已复制/);
  }, { navigator: { clipboard: { async writeText(value) { text = value; } } } });
  assert.match(text, /商品榜首页/);
  await withTool(savedData(), async ({ el }) => {
    await el('update-copy').listeners.click();
    assert.match(el('copy-status').textContent, /请选中下方文字复制/);
  });
});

test('missing cache requests collection without silently rendering demos', () => {
  withTool(undefined, ({ el }) => {
    assert.equal(el('saved').disabled, true);
    assert.equal(el('preview').srcdoc, '');
    assert.match(el('status').textContent, /还没有保存的真实榜单.*无需填写模板/);
  });
});

test('product links are visible on cards while missing and unsafe URLs remain explicit', () => {
  const data = savedData(); data.products[0].product.link = 'https://example.com/product/test-0';
  data.products[1].product.link = 'javascript:alert(1)';
  withTool(data, ({ el }) => {
    const cards = el('cards').innerHTML;
    assert.match(cards, /class="button product-link" href="https:\/\/example.com\/product\/test-0"/);
    assert.match(cards, /<h2><a class="product-title" href="https:\/\/example.com\/product\/test-0"[^>]*>已保存的女款裤子<\/a><\/h2>/);
    assert.match(el('preview').srcdoc, /<h3><a class="product-title" href="https:\/\/example.com\/product\/test-0"/);
    assert.ok(cards.indexOf('打开商品') < cards.indexOf('<details>'));
    assert.match(cards, /商品链接暂缺/);
    assert.match(cards, /复制商品名/);
    assert.doesNotMatch(cards, /href="javascript:/);
  });
});

test('desktop and exported page show the source price band separately from unknown SKU minimum', () => {
  const data = savedData();
  data.products[0].product.price_band_display = '价格带 ¥99–¥119';
  data.products[0].product.price_display = '旧的价格文字';
  withTool(data, ({ el }) => {
    assert.match(el('cards').innerHTML, /<span class="price-label">价格带<\/span>¥99–¥119/);
    assert.doesNotMatch(el('cards').innerHTML, /价格带 价格带|旧的价格文字/);
    assert.match(el('preview').srcdoc, /价格带：¥99–¥119/);
    assert.match(el('preview').srcdoc, /最低可购买价待验证/);
  });
});

test('product name and ID copy without guessed links, with selectable fallback', async () => {
  const copied = [];
  await withTool(savedData(), async ({ el }) => {
    for (const field of ['name', 'id']) {
      await el('cards').listeners.click({ target: { closest: selector => selector === '[data-copy-product]' ? { dataset: { copyProduct: 'test-0', copyField: field } } : null } });
    }
    assert.equal(el('copy-fallback').hidden, true);
    assert.doesNotMatch(el('cards').innerHTML, /class="button product-link"/);
  }, { navigator: { clipboard: { async writeText(text) { copied.push(text); } } } });
  assert.deepEqual(copied, ['已保存的女款裤子', 'test-0']);
  await withTool(savedData(), async ({ el }) => {
    await el('cards').listeners.click({ target: { closest: selector => selector === '[data-copy-product]' ? { dataset: { copyProduct: 'test-1', copyField: 'id' } } : null } });
    assert.equal(el('copy-fallback').hidden, false);
    assert.equal(el('copy-value').value, 'test-1');
    assert.match(el('status').textContent, /未允许自动复制/);
  });
});

test('corrupt or demo cache stays visibly unavailable', () => {
  const demo = savedData(); demo.meta.is_demo = true;
  for (const contents of ['{broken', demo]) {
    withTool(contents, ({ el }) => {
      assert.equal(el('saved').disabled, true);
      assert.equal(el('preview').srcdoc, '');
      assert.match(el('status').textContent, /读取失败/);
      assert.equal(el('status').className, 'error');
    });
  }
});

test('desktop update uses its own login bridge and newly collected data replaces the bundled ranking', async () => {
  const commands = [];
  await withTool(savedData(), async ({ el, context }) => {
    assert.equal(el('update-copy').textContent, '立即更新');
    await el('update-copy').listeners.click();
    assert.equal(commands[0].action, 'update-rankings');
    assert.deepEqual([...commands[0].price_queries], ['all']);
    el('desktop-login').listeners.click();
    assert.equal(commands[1].action, 'open-compass');
    assert.match(el('collection-help').textContent, /切换价位先筛选本地数据/);
    const snapshot = {
      schema: 'compass-product-dom-v1', source_url: 'https://compass.jinritemai.com/shop/chance/rank-product',
      observed_identity: '客户端新店铺', headers: ['排名', '商品', '店铺名称', '用户支付金额', '点击次数', '成交件数', '点击成交转化率', '操作'],
      category_path: ['服饰内衣', '服装', '女装', '牛仔裤'], dates: ['2026/10/06', '2026/10/12'], selected_tabs: ['总榜', '近7天'],
      page_number: 1, total_text: '共200条', rows: [{row_key: '1234567890123456789_1', rank_text: '', cells: ['', '', '', '100万', '1万', '1000', '10%', ''], product_name: '客户端新款', shop_name: '新商家', price_band: '¥99-¥119', product_link: 'https://example.com/observed-product'}],
    };
    const prepared = context.pantsDesktop.prepareSnapshot([], snapshot);
    assert.equal(prepared.data.products.length, 1);
    context.pantsDesktop.loadSnapshots(prepared.snapshots);
    assert.match(el('cards').innerHTML, /客户端新款/);
    assert.doesNotMatch(el('cards').innerHTML, /已保存的女款裤子/);
    assert.match(el('source').textContent, /客户端新店铺/);
    el('demo').listeners.click(); el('saved').listeners.click();
    assert.match(el('cards').innerHTML, /客户端新款/);
    assert.doesNotMatch(el('cards').innerHTML, /已保存的女款裤子/);
  }, {desktop: true, chrome: {webview: {postMessage: command => commands.push(command)}}});
});

test('price filtering stays local until explicit update and keeps selected bands and presets',()=>{
  const commands=[],data=savedData();
  data.products[0].product.price_band_display='¥80–¥99';data.products[1].product.price_band_display='¥209–¥229';
  withTool(data,({el,context})=>{
    el('band-70-99').listeners.click();
    assert.match(el('cards').innerHTML,/已保存的女款裤子/);
    assert.doesNotMatch(el('cards').innerHTML,/已保存的男款裤子/);
    assert.equal(commands.length,0);
    assert.deepEqual([...context.pantsDesktop.getUpdateOptions().price_queries],['70-99']);
    el('band-150+').listeners.click();
    assert.match(el('cards').innerHTML,/已保存的男款裤子/);
    assert.equal(commands.length,0);
    assert.deepEqual([...context.pantsDesktop.getUpdateOptions().price_queries],['70-99','150+']);
    el('save-price-preset').listeners.click();
    el('price-all').listeners.click();
    assert.equal(commands.length,0);
    assert.deepEqual([...context.pantsDesktop.getUpdateOptions().price_queries],['all']);
    el('price-preset').value='0';el('price-preset').listeners.change();
    assert.match(el('custom-ranges').value,/70-99.*150以上/);
    el('update-copy').listeners.click();
    assert.equal(commands.length,1);
    // Restoring a preset uses exact custom intervals; boundary-overlapping
    // native bands are fetched as well, then filtered locally.
    assert.deepEqual([...commands[0].price_queries],['50-70','70-99','99-150','150+']);
    context.pantsDesktop.setUpdateState({busy:true,message:'正在读取',error:false});
    assert.equal(el('update-copy').disabled,true);assert.equal(el('update-stop').hidden,false);
    context.pantsDesktop.navigate('settings');assert.equal(el('product-board').hidden,true);
    context.pantsDesktop.navigate('workbench');assert.equal(el('product-board').hidden,false);
    assert.equal(el('desktop-update').hidden,false);
    context.pantsDesktop.navigate('favorites');assert.equal(el('desktop-update').hidden,true);
  },{desktop:true,chrome:{webview:{postMessage:x=>commands.push(x)}}});
});

test('fast ranking mode persists, reports its scope, and is disabled during collection',()=>{
  const storage=new Map(),commands=[];
  const desktop={desktop:true,storage,chrome:{webview:{postMessage:x=>commands.push(x)}}};
  withTool(savedData(),({el,context})=>{
    assert.equal(context.pantsDesktop.getUpdateOptions().collect_links,true);
    el('fast-ranking').checked=true;el('fast-ranking').listeners.change();
    el('update-scope').value='all';el('update-limit').value='50';el('update-limit').listeners.change();
    assert.match(el('update-summary').textContent,/14 类 × 1 个价位 · 最多 700 条/);
    assert.match(el('update-plan').textContent,/快速读榜跳过逐件补链接/);
    assert.equal(commands.length,0);
    el('update-copy').listeners.click();
    assert.equal(commands[0].collect_links,false);
    context.pantsDesktop.setUpdateState({busy:true,message:'正在读取',error:false});
    assert.equal(el('fast-ranking').disabled,true);
    context.pantsDesktop.setUpdateState({busy:false,message:'已停止',error:false});
    assert.equal(el('fast-ranking').disabled,false);
  },desktop);
  withTool(savedData(),({el,context})=>{
    assert.equal(el('fast-ranking').checked,true);
    assert.equal(context.pantsDesktop.getUpdateOptions().collect_links,false);
    assert.match(el('update-summary').textContent,/最多 700 条/);
    el('custom-ranges').value='不正确的范围';
    el('update-copy').listeners.click();
    assert.equal(commands.length,1);
    assert.match(el('update-progress').textContent,/未开始更新/);
  },desktop);
});

test('custom visible apparel categories are selectable and unknown categories never enter a request',()=>{
  const commands=[],storage=new Map();
  const desktop={desktop:true,storage,chrome:{webview:{postMessage:x=>commands.push(x)}}};
  withTool(savedData(),({el,context})=>{
    const paths=[['服饰内衣','服装','女装','测试上衣'],['服饰内衣','服装','男装','测试外套']];
    context.pantsDesktop.setCategories(paths);
    el('update-scope').value='custom';el('update-scope').listeners.change();
    assert.equal(el('custom-category-panel').hidden,false);
    el('update-copy').listeners.click();
    assert.equal(commands.length,0);
    assert.match(el('update-progress').textContent,/勾选/);
    el('category-choices').listeners.click({target:{closest:()=>({dataset:{category:'0'}})}});
    el('update-copy').listeners.click();
    assert.equal(commands.length,1);
    assert.deepEqual(JSON.parse(JSON.stringify(commands[0].category_paths)),[paths[0]]);
    assert.match(el('category-feedback').textContent,/2 个服装类目/);
    assert.throws(()=>context.pantsDesktop.setCategories([['食物','零食','女装','上衣']]),/未替换原类目/);
  },desktop);
  withTool(savedData(),({context})=>{
    const options=context.pantsDesktop.getUpdateOptions();
    assert.equal(options.preset,'custom');
    assert.equal(options.category_paths[0][3],'测试上衣');
  },desktop);
});

test('factory shortlist explains visible evidence, excludes unknowns and exports only current matches',()=>{
  const data=savedData();
  data.products[0].metrics={sales_count:'100-500',click_conversion_rate:'3%-8%'};
  data.products[1].metrics={sales_count:'1000-2500'};
  withTool(data,({el})=>{
    el('factory-starter').listeners.click();
    assert.match(el('cards').innerHTML,/已保存的女款裤子/);
    assert.doesNotMatch(el('cards').innerHTML,/已保存的男款裤子/);
    assert.match(el('cards').innerHTML,/成交下限 100 件，达标/);
    assert.match(el('preview').srcdoc,/工厂初筛/);
    el('factory-only').checked=false;el('factory-only').listeners.change();
    assert.match(el('cards').innerHTML,/资料不足 · 待核实/);
    el('factory-clear').listeners.click();
    assert.match(el('cards').innerHTML,/已保存的男款裤子/);
    assert.doesNotMatch(el('cards').innerHTML,/factory-assessment/);
  });
});
