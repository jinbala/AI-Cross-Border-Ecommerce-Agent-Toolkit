import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeCompassSnapshots } from '../scripts/normalize_compass_snapshot.mjs';
import { mergeCompassSnapshot } from '../scripts/compass_core.mjs';
import { buildSelectionReport, renderSelectionHtml } from '../scripts/selection_core.mjs';

function snapshot() {
  return {
    schema: 'compass-product-dom-v1',
    source_url: 'https://compass.jinritemai.com/shop/chance/rank-product',
    observed_identity: '测试店铺',
    headers: ['排名', '商品', '店铺名称', '用户支付金额', '点击次数', '成交件数', '点击成交转化率', '操作'],
    category_path: ['服饰内衣', '服装', '女装', '牛仔裤'],
    dates: ['2026/10/06', '2026/10/12'], selected_tabs: ['总榜', '近7天'],
    page_number: 1, total_text: '共200条',
    rows: [{
      row_key: '1000000000000000001_1', rank_text: '',
      cells: ['3', '测试商品', '测试商家', '100万 - 250万', '10万 - 25万', '1万 - 2.5万', '10% - 20%', '查看详情'],
      product_name: '测试商品', shop_name: '测试商家', price_band: '100 - 200',
      product_link: '', details_available: false,
    }],
  };
}

test('DOM normalization preserves evidence, icon rank, payment ranges and unknown SKU price', () => {
  const data = normalizeCompassSnapshots([snapshot()], '测试店铺');
  const item = data.products[0];
  assert.equal(item.rank, 1); // 排名图标为空；单元格文字 3 是排名变化。
  assert.equal(item.source_evidence.rank_cell_text, '3');
  assert.equal(item.product.id, '1000000000000000001');
  assert.equal(item.product.price_min, null);
  assert.equal(item.product.price_band_display, '100–200');
  assert.equal(item.product.link, '');
  assert.equal(item.metrics.payment_amount, '100万–250万');
  assert.equal(data.meta.ranking_date, '2026-10-12');
  assert.equal(data.coverage[0].status, 'partial');
  const report = buildSelectionReport(data);
  const html = renderSelectionHtml(report);
  assert.equal(report.groups.length, 1);
  assert.match(html, /用户支付金额/);
  assert.match(html, /点击次数/);
  assert.match(html, /点击成交转化率/);
  assert.match(html, /服饰内衣 \/ 服装 \/ 女装 \/ 牛仔裤/);
  assert.match(html, /真实页面采集/);
  assert.doesNotMatch(html, /douyin\.com\/video/);
});

test('integrated apparel mode accepts visible clothing leaves while standalone pants mode stays strict',()=>{
  const source=snapshot();source.category_path[3]='测试上衣';
  assert.throws(()=>normalizeCompassSnapshots([source]),/男女裤/);
  const data=normalizeCompassSnapshots([source],undefined,{allowApparel:true});
  assert.equal(data.products[0].product.apparel.type,'测试上衣');
  for(const path of [['服饰内衣','服装','女装','全部'],['食品','零食','女装','测试上衣'],['服饰内衣','服装','未知','测试上衣']]) {
    const invalid=structuredClone(source);invalid.category_path=path;
    assert.throws(()=>normalizeCompassSnapshots([invalid],undefined,{allowApparel:true}));
  }
});

test('desktop rereads replace the same page and add other pages/categories without mutating old data', () => {
  const first = snapshot(), reread = snapshot(); reread.rows[0].price_band = '239';
  const result = mergeCompassSnapshot([first], reread);
  assert.equal(result.data.products.length, 1);
  assert.equal(result.data.products[0].product.price_band_display, '239');
  assert.equal(first.rows[0].price_band, '100 - 200');
  const page2 = snapshot(); page2.page_number = 2; page2.rows[0].row_key = '9999999999999999999_11';
  const addedPage = mergeCompassSnapshot(result.snapshots, page2);
  assert.equal(addedPage.data.products.length, 2);
  assert.equal(addedPage.data.coverage[0].pages, 2);
  const male = snapshot(); male.category_path = ['服饰内衣', '服装', '男装', '休闲裤'];
  assert.equal(mergeCompassSnapshot(addedPage.snapshots, male).data.products.length, 3);
});

test('desktop account or period changes start a fresh collection; invalid capture never replaces valid pages', () => {
  const previous = [snapshot()];
  for (const mutate of [s => { s.observed_identity = '新店铺'; }, s => { s.dates = ['2026/10/07', '2026/10/13']; }, s => { s.selected_tabs[1] = '近30天'; }]) {
    const next = snapshot(); mutate(next);
    const result = mergeCompassSnapshot(previous, next);
    assert.equal(result.snapshots.length, 1);
    assert.equal(result.replaced_context, true);
    assert.equal(result.data.meta.observed_identity, next.observed_identity);
  }
  const invalid = snapshot(); invalid.headers = ['未知表头'];
  assert.throws(() => mergeCompassSnapshot(previous, invalid), /表头/);
  assert.equal(previous[0].rows[0].product_link, '');
});

test('price query scopes keep separate page/rank evidence and explicit empty results differ from failed reads',()=>{
  const a=snapshot(), b=snapshot();
  a.source_filters={price_band:'70-99',price_band_label:'70–99 元'};
  b.source_filters={price_band:'99-150',price_band_label:'99–150 元'};
  const combined=normalizeCompassSnapshots([a,b]);
  assert.equal(combined.coverage.length,2);
  assert.equal(combined.expected_nodes.length,1);
  const report=buildSelectionReport(combined,{price_basis:'price_band',price_ranges:[]});
  assert.equal(report.groups.length,1);
  assert.equal(report.groups[0].observations.length,2);
  const empty=snapshot();empty.rows=[];empty.page_number=null;empty.total_text='共0条';empty.empty_state_text='暂无数据';
  assert.equal(normalizeCompassSnapshots([empty]).products.length,0);
  delete empty.empty_state_text;
  assert.throws(()=>normalizeCompassSnapshots([empty]),/读取成功/);
});

test('mixed identities, periods and repeated pages cannot silently merge', () => {
  for (const mutate of [
    b => { b.observed_identity = '另一店铺'; },
    b => { b.dates[0] = '2026/10/05'; },
    b => { b.selected_tabs[1] = '近30天'; },
  ]) {
    const b = snapshot(); mutate(b);
    assert.throws(() => normalizeCompassSnapshots([snapshot(), b]), /不能合并/);
  }
  assert.throws(() => normalizeCompassSnapshots([snapshot(), snapshot()]), /页码重复/);
  assert.throws(() => normalizeCompassSnapshots([snapshot()], '错误店铺'), /身份/);
});

test('changed headers, non-pants categories, invalid dates and inconsistent ranks fail closed', () => {
  for (const mutate of [
    b => { b.headers[3] = '成交金额'; },
    b => { b.category_path[3] = 'T恤'; },
    b => { b.dates[0] = '2026/02/30'; },
    b => { b.rows[0].rank_text = '2'; },
    b => { b.rows[0].row_key = '3.77E+18_1'; },
  ]) {
    const b = snapshot(); mutate(b);
    assert.throws(() => normalizeCompassSnapshots([b]));
  }
});

test('additional pages retain category coverage and separate male/female paths', () => {
  const page2 = snapshot(); page2.page_number = 2;
  page2.rows[0].row_key = '3770640078863466654_11'; page2.rows[0].rank_text = '11';
  const male = snapshot(); male.category_path = ['服饰内衣', '服装', '男装', '休闲裤'];
  const data = normalizeCompassSnapshots([snapshot(), page2, male]);
  assert.equal(data.products.length, 3);
  assert.equal(data.coverage.length, 2);
  assert.equal(data.coverage[0].pages, 2);
  assert.deepEqual(data.coverage[0].page_numbers, [1, 2]);
  assert.equal(data.products[2].product.apparel.gender, '男款');
  assert.equal(data.coverage[0].reached_top_200_or_end, false);
});
