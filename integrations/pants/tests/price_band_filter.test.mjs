import assert from 'node:assert/strict';
import test from 'node:test';
import { parseProductPriceBand, buildSelectionReport } from '../scripts/selection_core.mjs';
import { parseCustomPriceRanges, compassQueriesForRanges } from '../scripts/price_ranges.mjs';

test('price-band parser accepts source currency/range formats and fails safely on ambiguous values', () => {
  for (const [text, expected] of [
    ['价格带 ¥99–¥119', { min: 99, max: 119 }],
    ['价格带：￥1,000.50 - ￥2,999', { min: 1000.5, max: 2999 }],
    ['¥379', { min: 379, max: 379 }],
    ['99元 至 119元', { min: 99, max: 119 }],
    ['¥0～¥100', { min: 0, max: 100 }],
  ]) assert.deepEqual(parseProductPriceBand({ price_band_display: text }), expected);
  for (const text of ['待验证', '¥119–¥99', '-99', '¥1万以上', '¥1,00', '1e3', '99/119']) {
    assert.equal(parseProductPriceBand({ price_band_display: text }), null);
  }
  assert.equal(parseProductPriceBand({ price_display: '¥99–¥119' }), null);
});

test('multiple disjoint price bands use OR, keep source prices and deduplicate cards across query scopes', () => {
  const input = {meta: {source_type: 'product_ranking', ranking_date: '2026-10-12'}, products: [
    ...[45, 85, 110, 190, 240].map((price, i) => ({ranking_date: '2026-10-12', rank: i+1, category_path: ['裤装'], product: {id:String(i),name:'测试款',price_band_display:'¥'+price,price_min:null}})),
    {ranking_date:'2026-10-12',rank:1,category_path:['裤装'],source_filters:{price_band:'99-150'},product:{id:'2',name:'测试款',price_band_display:'¥110',price_min:null}},
  ]};
  const report = buildSelectionReport(input,{price_basis:'price_band',price_ranges:[{min:80,max:120},{min:180,max:200}]});
  assert.equal(report.groups.length,3);
  assert.deepEqual(new Set(report.groups.map(g=>g.product.id)), new Set(['1','2','3']));
  assert.equal(report.groups.find(g=>g.product.id==='2').observations.length,2);
  assert.ok(report.groups.every(g=>g.product.price_min===null));
  assert.equal(buildSelectionReport(input,{price_basis:'price_band',price_ranges:[]}).groups.length,5);
  assert.equal(buildSelectionReport(input,{price_basis:'price_band',price_ranges:[{min:200,max:null}]}).groups.length,1);
  assert.throws(()=>buildSelectionReport(input,{price_ranges:[{min:120,max:80}]}),/区间/);
});

test('custom price input validates separate ranges and queries the covering native price bands',()=>{
  const ranges=parseCustomPriceRanges('80-120；180-250');
  assert.deepEqual(ranges,[{min:80,max:120},{min:180,max:250}]);
  assert.deepEqual(compassQueriesForRanges(ranges),['70-99','99-150','150+']);
  assert.deepEqual(parseCustomPriceRanges('150以上'),[{min:150,max:null}]);
  assert.deepEqual(compassQueriesForRanges([]),['all']);
  for(const value of ['120-80','1e3-2000','-50-99','foo']) assert.throws(()=>parseCustomPriceRanges(value));
});

test('explicit band filtering uses inclusive interval overlap without inventing a minimum SKU price', () => {
  const products = ['价格带 ¥99–¥119', '价格带 ¥199–¥219', '价格带 ¥239', '价格带 ¥69–¥99', '未核实'].map((band, index) => ({
    ranking_date: '2026-10-12', category_path: ['测试裤装'], rank: index + 1,
    product: { id: String(index), name: '测试裤子' + index, price_band_display: band, price_min: null },
  }));
  const input = { meta: { source_type: 'product_ranking', ranking_date: '2026-10-12' }, products };
  const report = buildSelectionReport(input, { price_floor: 100, price_ceiling: 200, price_basis: 'price_band' });
  assert.deepEqual(report.groups.map(group => group.product.id), ['0', '1', '4']);
  assert.equal(report.summary.price_excluded, 2);
  assert.equal(report.groups[0].price_filter_basis, 'price_band');
  assert.equal(report.groups[2].price_filter_basis, 'unknown');
  assert.equal(report.groups[0].product.price_min, null);
  assert.match(report.meta.price_rule, /有交集/);
  assert.equal(buildSelectionReport(input, { price_floor: 100, price_ceiling: 200 }).groups.length, 5);
  assert.throws(() => buildSelectionReport(input, { price_basis: 'guessed' }), /price_basis/);
});

test('band mode falls back to a known SKU minimum only when the page band is unavailable', () => {
  const input = { meta: { source_type: 'product_ranking', ranking_date: '2026-10-12' }, products: [
    { ranking_date: '2026-10-12', product: { id: 'known', name: '测试裤子', price_min: 150 } },
    { ranking_date: '2026-10-12', product: { id: 'high', name: '测试裤子', price_min: 250 } },
  ] };
  const report = buildSelectionReport(input, { price_floor: 100, price_ceiling: 200, price_basis: 'price_band' });
  assert.deepEqual(report.groups.map(group => group.product.id), ['known']);
  assert.equal(report.groups[0].price_filter_basis, 'sku_min');
});
