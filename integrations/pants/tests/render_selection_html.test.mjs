import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

import {
  buildSelectionReport,
  choosePrimaryWork,
  repeatTier,
  renderSelectionHtml,
  sortGroupsByRank,
  sortWorksByRank,
} from '../scripts/render_selection_html.mjs';

const work = ({
  productId,
  workId,
  rank,
  publishedAt = '2026-08-19T12:00:00+08:00',
  isNew = true,
  priceMin = 99,
  category = ['个护家清', '个人护理', '身体清洁', '全部'],
}) => ({
  ranking_date: '2026-08-20',
  category_path: category,
  rank,
  is_new: isNew,
  product: {
    id: productId,
    name: `商品${productId}`,
    price_display: priceMin == null ? '待验证' : `¥${priceMin}`,
    price_min: priceMin,
    link: `https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?id=${productId}`,
  },
  work: {
    id: workId,
    title: `作品${workId}`,
    author: `作者${workId}`,
    account: `账号${workId}`,
    published_at: publishedAt,
  },
  metrics: {
    transaction_amount: '¥2,500–¥5,000',
    sales_count: '0–25',
    views: '7.5万–10万',
    likes: '100–250',
  },
});

test('filters the ranking-date three-day window and only excludes price above ¥1000', () => {
  const input = {
    meta: { ranking_date: '2026-08-20', generated_at: '2026-08-21T09:00:00+08:00' },
    coverage: [],
    relations: [
      work({ productId: 'keep-range', workId: '1', rank: 2, priceMin: 999 }),
      work({ productId: 'drop-price', workId: '2', rank: 1, priceMin: 1000.01 }),
      work({ productId: 'keep-missing-price', workId: '3', rank: 3, priceMin: null }),
      work({ productId: 'drop-old', workId: '4', rank: 4, publishedAt: '2026-08-17T23:59:00+08:00' }),
      work({ productId: 'drop-not-new', workId: '5', rank: 5, isNew: false }),
      work({ productId: 'unresolved-date', workId: '6', rank: 6, publishedAt: 'not-a-date' }),
    ],
  };

  const report = buildSelectionReport(input);
  assert.deepEqual(report.groups.map((group) => group.product.id), ['keep-range', 'keep-missing-price']);
  assert.equal(report.summary.price_excluded, 1);
  assert.equal(report.summary.outside_window, 1);
  assert.equal(report.summary.not_new, 1);
  assert.equal(report.unresolved.length, 1);
  assert.equal(report.groups[1].price_status, '待验证');
  assert.deepEqual(report.meta.publish_window, ['2026-08-18', '2026-08-20']);
});

test('deduplicates product/work relations, keeps first category, and groups repetition', () => {
  const first = work({ productId: 'p1', workId: 'w1', rank: 10 });
  const duplicateOtherCategory = work({
    productId: 'p1',
    workId: 'w1',
    rank: 10,
    category: ['智能家居', '居家日用', '日常护理', '全部'],
  });
  const second = work({ productId: 'p1', workId: 'w2', rank: 4, publishedAt: '2026-08-18T09:00:00+08:00' });
  const report = buildSelectionReport({
    meta: { ranking_date: '2026-08-20' },
    coverage: [],
    relations: [first, duplicateOtherCategory, second],
  });

  assert.equal(report.groups.length, 1);
  assert.equal(report.groups[0].works.length, 2);
  assert.equal(report.groups[0].repeat_tier, '重复出现');
  assert.deepEqual(report.groups[0].works.find((item) => item.work.id === 'w1').category_path, first.category_path);
  assert.equal(report.summary.duplicate_relations, 1);
});

test('uses best rank as representative and applies deterministic ranking tie-breakers', () => {
  const works = [
    work({ productId: 'p', workId: 'older', rank: 7, publishedAt: '2026-08-18T09:00:00+08:00' }),
    work({ productId: 'p', workId: 'newer', rank: 7, publishedAt: '2026-08-20T09:00:00+08:00' }),
    work({ productId: 'p', workId: 'best', rank: 3, publishedAt: '2026-08-18T08:00:00+08:00' }),
  ];
  assert.equal(choosePrimaryWork(works).work.id, 'best');
  assert.deepEqual(sortWorksByRank(works).map((item) => item.work.id), ['best', 'newer', 'older']);

  const groups = [
    { product: { id: 'b' }, primary_work: works[0], works: [works[0]] },
    { product: { id: 'a' }, primary_work: works[1], works: [works[1], works[2]] },
  ];
  assert.deepEqual(sortGroupsByRank(groups).map((group) => group.product.id), ['a', 'b']);
  assert.equal(repeatTier(1), '单次出现');
  assert.equal(repeatTier(2), '重复出现');
  assert.equal(repeatTier(3), '多作品出现');
  assert.equal(repeatTier(5), '高频出现');
});

test('renders a single-file warehouse audit page with coverage, radar, links, and no markdown dependency', () => {
  const unsafeProductLink = work({ productId: 'p2', workId: 'w3', rank: 9 });
  unsafeProductLink.product.link = 'javascript:alert(1)';
  const report = buildSelectionReport({
    meta: { ranking_date: '2026-08-20' },
    coverage: [{ category_path: ['个护家清', '个人护理', '全部'], status: 'complete', attempts: 1 }],
    relations: [
      work({ productId: 'p1', workId: 'w1', rank: 2 }),
      work({ productId: 'p1', workId: 'w2', rank: 5 }),
      unsafeProductLink,
    ],
  });
  const html = renderSelectionHtml(report);

  for (const token of ['#F7F8F6', '#17191A', '#F0C62E', '重复商品观察', '覆盖稽核', '完整产品清单']) {
    assert.match(html, new RegExp(token, 'i'));
  }
  assert.match(html, /https:\/\/www\.douyin\.com\/video\/w1/);
  assert.match(html, /haohuo\.jinritemai\.com/);
  assert.match(html, /data-product-id="p1"/);
  assert.match(html, /aria-expanded="false"/);
  assert.doesNotMatch(html, /href="javascript:alert/);
  assert.match(html, /商品链接待验证/);
  assert.doesNotMatch(html, /linear-gradient|radial-gradient/);
});

test('CLI writes the required dated HTML filename', () => {
  const dir = mkdtempSync(join(tmpdir(), 'selection-skill-'));
  try {
    const inputPath = join(dir, 'input.json');
    writeFileSync(inputPath, JSON.stringify({
      meta: { ranking_date: '2026-08-20' },
      coverage: [],
      relations: [work({ productId: 'p1', workId: 'w1', rank: 1 })],
    }));
    const result = spawnSync(process.execPath, ['scripts/render_selection_html.mjs', inputPath, '--output-dir', dir], {
      cwd: new URL('..', import.meta.url),
      encoding: 'utf8',
    });
    assert.equal(result.status, 0, result.stderr);
    const output = join(dir, '选品结果-2026-08-20-近3日.html');
    assert.match(readFileSync(output, 'utf8'), /商品p1/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
