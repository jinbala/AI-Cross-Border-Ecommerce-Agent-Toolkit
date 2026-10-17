import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
import { buildSelectionReport, renderSelectionHtml } from '../scripts/selection_core.mjs';
import { CSV_HEADERS, PRODUCT_CSV_HEADERS, importCsv, parseCsv } from '../scripts/import_selection.mjs';

const demo = JSON.parse(readFileSync(new URL('./fixtures/pants-demo.json', import.meta.url), 'utf8'));
const row = (patch = {}) => ({ ...structuredClone(demo.relations[0]), ...patch });
const input = (relations) => ({ meta: { ranking_date: '2026-10-12' }, relations });

test('custom price/date/gender rules honor boundaries and keep unknown prices', () => {
  const a = row(); a.product.price_min = 300;
  const b = row(); b.product.id = 'b'; b.work.id = 'b'; b.product.price_min = 300.01;
  const c = row(); c.product.id = 'c'; c.work.id = 'c'; c.product.price_min = null;
  const old = row(); old.product.id = 'old'; old.work.id = 'old'; old.work.published_at = '2026-10-11';
  const report = buildSelectionReport(input([a, b, c, old]), { publication_days: 1, price_floor: 100, price_ceiling: 300, gender: '女款' });
  assert.deepEqual(report.groups.map(group => group.product.id).sort(), ['DEMO-W01', 'c'].sort());
  assert.equal(report.summary.price_excluded, 1);
  assert.equal(report.summary.outside_window, 1);
  assert.deepEqual(report.meta.publish_window, ['2026-10-12', '2026-10-12']);
  assert.match(renderSelectionHtml(report), /近1日新上榜选品/);
  assert.match(renderSelectionHtml(report), /¥100–¥300/);
});

test('Shanghai calendar conversion and invalid calendar/time values', () => {
  const utc = row(); utc.work.published_at = '2026-10-09T18:00:00Z';
  assert.equal(buildSelectionReport(input([utc])).groups[0].works[0].publish_date, '2026-10-10');
  for (const date of ['2026-02-30', '2026-10-12T99:00:00+08:00', '2026-10-12garbage']) {
    const bad = row(); bad.work.published_at = date;
    assert.equal(buildSelectionReport(input([bad])).unresolved.length, 1);
  }
  assert.throws(() => buildSelectionReport({ meta: { ranking_date: '2026-10-12junk' }, relations: [] }));
});

test('ranking-date mismatch and unknown requested gender do not silently qualify', () => {
  const stale = row({ ranking_date: '2026-10-11' });
  const unknown = row(); unknown.product.id = 'unknown'; unknown.work.id = 'unknown'; delete unknown.product.apparel.gender;
  const report = buildSelectionReport(input([stale, unknown]), { gender: '女款' });
  assert.equal(report.groups.length, 0);
  assert.equal(report.unresolved.length, 2);
  assert.equal(buildSelectionReport(input([unknown])).groups.length, 1);
});

test('new-entry override is explicit and validates booleans and configuration', () => {
  const notNew = row({ is_new: false });
  assert.equal(buildSelectionReport(input([notNew])).groups.length, 0);
  const report = buildSelectionReport(input([notNew]), { require_new_entry: false });
  assert.equal(report.groups.length, 1);
  assert.match(renderSelectionHtml(report), /发布作品观察/);
  for (const config of [{ publication_days: 0 }, { publication_days: 2.5 }, { price_ceiling: -1 }, { price_floor: 300, price_ceiling: 100 }, { require_new_entry: 'false' }]) {
    assert.throws(() => buildSelectionReport(input([]), config));
  }
});

test('distinct known account count is separate from work count', () => {
  const report = buildSelectionReport(demo);
  assert.equal(report.groups[0].repeat_count, 3);
  assert.equal(report.groups[0].account_count, 1);
  assert.equal(report.groups[0].repeat_tier, '多作品出现');
  const missing = row(); missing.work.account = '';
  assert.equal(buildSelectionReport(input([missing])).groups[0].missing_account_count, 1);
});

test('coverage needs an expected plan and traversal evidence for all nodes', () => {
  const data = input([]);
  assert.equal(buildSelectionReport(data).coverage_state.complete, false);
  data.expected_nodes = [['男裤'], ['女裤']];
  data.coverage = [{ category_path: ['男裤'], status: 'complete', reached_top_200_or_end: true }];
  assert.deepEqual(buildSelectionReport(data).coverage_state.missing_nodes, [['女裤']]);
  data.coverage.push({ category_path: ['女裤'], status: 'complete' });
  assert.equal(buildSelectionReport(data).coverage_state.complete, false);
  data.coverage[1].reached_top_200_or_end = true;
  assert.equal(buildSelectionReport(data).coverage_state.complete, true);
  data.failed_nodes = [{ category_path: ['男裤'], reason: '失败' }];
  assert.equal(buildSelectionReport(data).coverage_state.complete, false);
});

test('demo notice suppresses fictional work links; real links escape untrusted text', () => {
  const html = renderSelectionHtml(buildSelectionReport(demo));
  assert.match(html, /演示数据/);
  assert.doesNotMatch(html, /href="https:\/\/www.douyin.com\/video\/DEMO/);
  const hostile = row(); hostile.product.name = '</script><img src=x onerror=alert(1)>';
  hostile.product.apparel.fit = '" onmouseover="alert(1)'; hostile.product.link = 'javascript:alert(1)';
  const escaped = renderSelectionHtml(buildSelectionReport(input([hostile])));
  assert.doesNotMatch(escaped, /<img src=x/);
  assert.doesNotMatch(escaped, /href="javascript:/);
  assert.match(escaped, /&lt;\/script&gt;/);
  new vm.Script(escaped.match(/<script>([\s\S]*?)<\/script>/)[1]);
});

test('CSV supports UTF-8 BOM, quotes, multiline fields and exact long string IDs', () => {
  const values = Object.fromEntries(CSV_HEADERS.map(name => [name, '']));
  Object.assign(values, { 榜单日期: '2026-10-12', 商品ID: '12345678901234567890', 作品ID: '7674483845189681009', 商品名称: '裤子,"款式"\n第二行', 发布时间: '2026-10-12T10:00:00+08:00', 新上榜: '是', 最低价: '129', 款别: '女款' });
  const quote = value => '"' + value.replaceAll('"', '""') + '"';
  const csv = '\uFEFF' + CSV_HEADERS.join(',') + '\r\n' + CSV_HEADERS.map(name => quote(values[name])).join(',');
  const data = importCsv(csv);
  assert.equal(data.relations[0].product.id, values['商品ID']);
  assert.equal(data.relations[0].work.id, values['作品ID']);
  assert.equal(data.relations[0].product.name, values['商品名称']);
  assert.equal(buildSelectionReport(data).groups.length, 1);
  assert.throws(() => parseCsv('a,"unterminated'));
  assert.throws(() => importCsv('榜单日期,商品ID,作品ID,发布时间,新上榜\n2026-10-12,a,b,c'));
  assert.throws(() => importCsv('商品ID,商品ID'));
  const numericId = row(); numericId.work.id = 7674483845189681009;
  assert.throws(() => buildSelectionReport(input([numericId])), /必须是文本/);
  numericId.work.id = '7.674483845E+18';
  assert.throws(() => buildSelectionReport(input([numericId])), /科学计数法/);
});

test('CLI applies config file and uses the effective day count in filename', () => {
  const directory = mkdtempSync(join(tmpdir(), 'pants-config-test-'));
  try {
    const configPath = join(directory, 'config.json');
    writeFileSync(configPath, JSON.stringify({ publication_days: 7, price_ceiling: 250 }));
    const result = spawnSync(process.execPath, ['scripts/render_selection_html.mjs', 'tests/fixtures/pants-demo.json', '--config', configPath, '--output-dir', directory], { cwd: new URL('..', import.meta.url), encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const html = readFileSync(join(directory, '选品结果-2026-10-12-近7日.html'), 'utf8');
    assert.match(html, /演示数据/);
    assert.match(html, /近7日新上榜选品/);
    assert.match(html, /¥0–¥250/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('offline tool compiles and demo/config-error actions produce the right download state', async () => {
  const build = spawnSync(process.execPath, ['scripts/build_local_tool.mjs'], { cwd: new URL('..', import.meta.url), encoding: 'utf8' });
  assert.equal(build.status, 0, build.stderr);
  const html = readFileSync(new URL('../results/pants-tool.html', import.meta.url), 'utf8');
  const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { _value: '', get value() { return this._value; }, set value(value) { this._value = String(value); }, checked: false, disabled: true, textContent: '', srcdoc: '', files: [], listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; }, setAttribute(name, value) { this[name] = String(value); }, removeAttribute(name) { this[name] = ''; } });
    return elements.get(id);
  };
  const downloads = [];
  const context = vm.createContext({ document: { getElementById: element, createElement: () => ({ click() {} }) }, structuredClone, Blob, URL: { createObjectURL(blob) { downloads.push(blob); return 'blob:test'; }, revokeObjectURL() {} }, setTimeout: fn => fn(), console });
  new vm.Script(script).runInContext(context);
  assert.equal(element('source-type').value, 'product_ranking');
  assert.equal(element('days').disabled, true);
  element('demo').listeners.click();
  assert.match(element('preview').srcdoc, /男女裤商品榜选品/);
  assert.equal(element('download').disabled, false);
  element('source-type').value = 'graphic_ranking';
  element('source-type').listeners.input();
  element('demo').listeners.click();
  assert.match(element('preview').srcdoc, /女款高腰直筒牛仔裤/);
  assert.equal(element('download').disabled, false);
  element('template').listeners.click();
  assert.ok((await downloads[0].text()).startsWith('榜单日期,类目路径'));
  assert.ok(!(await downloads[0].text()).includes('\\uFEFF'));
  assert.ok((await downloads[0].text()).endsWith('\r\n'));
  element('days').value = '0';
  element('generate').listeners.click();
  assert.equal(element('download').disabled, true);
  assert.equal(element('preview').srcdoc, '');
  assert.match(element('status').textContent, /1–90/);
  element('days').value = '3';
  const uploaded = input([row()]);
  uploaded.relations[0].product.name = '用户导入的裤子';
  element('file').files = [{ name: 'real.json', text: async () => JSON.stringify(uploaded) }];
  await element('file').listeners.change({ target: element('file') });
  assert.equal(element('download').disabled, false);
  assert.match(element('preview').srcdoc, /用户导入的裤子/);
  assert.doesNotMatch(element('preview').srcdoc, /以下商品、账号和成交指标均为虚构/);
  element('file').files = [{ name: 'bad.json', text: async () => '{broken' }];
  await element('file').listeners.change({ target: element('file') });
  assert.equal(element('download').disabled, true);
  assert.equal(element('preview').srcdoc, '');
  element('generate').listeners.click();
  assert.match(element('status').textContent, /请先导入/);
});

test('product ranking accepts product evidence without works, publication dates or new markers', () => {
  const raw = JSON.parse(readFileSync(new URL('./fixtures/product-ranking-demo.json', import.meta.url), 'utf8'));
  const report = buildSelectionReport(raw);
  assert.equal(report.groups.length, 5);
  assert.equal(report.unresolved.length, 0);
  assert.equal(report.meta.publish_window, null);
  assert.deepEqual(report.meta.applied_filters, ['price', 'gender']);
  for (const group of report.groups) {
    assert.deepEqual(group.works, []);
    assert.equal(group.account_count, null);
    assert.equal(group.repeat_count, null);
    assert.equal(group.primary_work, null);
    assert.ok(group.primary_observation.product.id);
  }
  const html = renderSelectionHtml(report);
  assert.match(html, /男女裤商品榜选品/);
  assert.doesNotMatch(html, /代表作品：|已知推广账号|href="https:\/\/www.douyin.com\/video/);
  assert.doesNotMatch(html, /发布窗口|观看<|点赞</);
  new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
  raw.products.reverse();
  assert.equal(buildSelectionReport(raw).groups[0].primary_observation.rank, 1);
});

test('product CSV does not require graphic-only columns; price/gender filtering still works', () => {
  const values = Object.fromEntries(PRODUCT_CSV_HEADERS.map(name => [name, '']));
  Object.assign(values, { 榜单日期: '2026-10-12', 商品ID: '12345678901234567890', 商品名称: '测试女裤', 最低价: '129', 款别: '女款' });
  const csv = PRODUCT_CSV_HEADERS.join(',') + '\n' + PRODUCT_CSV_HEADERS.map(name => values[name]).join(',');
  const raw = importCsv(csv, undefined, 'product_ranking');
  assert.equal(raw.products[0].work, undefined);
  assert.equal(raw.products[0].is_new, undefined);
  assert.equal(buildSelectionReport(raw).groups.length, 1);
  assert.equal(buildSelectionReport(raw, { price_ceiling: 100 }).groups.length, 0);
  assert.equal(buildSelectionReport(raw, { gender: '男款' }).groups.length, 0);
  assert.throws(() => importCsv(csv), /作品ID/);
  assert.throws(() => buildSelectionReport({ meta: { source_type: 'shop_ranking' }, products: [] }), /不支持/);
});

test('report interactions filter apparel, clear filters and expand works', () => {
  const report = buildSelectionReport(demo);
  const html = renderSelectionHtml(report);
  const makeElement = (extra = {}) => ({ value: '', hidden: false, listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; }, ...extra });
  const elements = new Map();
  const get = (id) => { if (!elements.has(id)) elements.set(id, makeElement()); return elements.get(id); };
  const products = report.groups.map(group => {
    const works = group.works.map(work => makeElement({ dataset: { publishDate: work.publish_date, category: work.category_path.join(' / '), search: work.work.title.toLowerCase() } }));
    return makeElement({ dataset: { productSearch: group.product.name.toLowerCase(), repeat: String(group.repeat_count), ...group.product.apparel }, querySelectorAll: () => works });
  });
  get('product-list').querySelectorAll = () => products;
  const context = vm.createContext({ document: { getElementById: get, querySelectorAll: () => [] } });
  new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]).runInContext(context);
  get('gender-filter').value = '女款'; get('gender-filter').listeners.input();
  assert.equal(products.filter(product => !product.hidden).length, 3);
  get('fit-filter').value = '直筒'; get('fit-filter').listeners.input();
  assert.equal(products.filter(product => !product.hidden).length, 1);
  get('clear').listeners.click();
  assert.equal(products.filter(product => !product.hidden).length, 5);
  const attributes = { 'aria-controls': 'panel', 'aria-expanded': 'false' };
  const button = { getAttribute: key => attributes[key], setAttribute: (key, value) => { attributes[key] = value; } };
  get('panel').hidden = true;
  get('product-list').listeners.click({ target: { closest: () => button } });
  assert.equal(get('panel').hidden, false);
  assert.equal(attributes['aria-expanded'], 'true');
});
