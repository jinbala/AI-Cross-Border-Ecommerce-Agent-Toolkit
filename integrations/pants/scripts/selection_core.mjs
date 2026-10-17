export const DEFAULT_CONFIG = Object.freeze({
  publication_days: 3,
  price_floor: 0,
  price_ceiling: 1000,
  price_basis: 'sku_min',
  price_ranges: null,
  require_new_entry: true,
  timezone: 'Asia/Shanghai',
  gender: '全部',
});

export function normalizeConfig(raw = {}) {
  const config = { ...DEFAULT_CONFIG, ...raw };
  if (!Number.isInteger(config.publication_days) || config.publication_days < 1 || config.publication_days > 90) {
    throw new Error('发布时间窗口必须是 1–90 的整数');
  }
  for (const key of ['price_floor', 'price_ceiling']) {
    if (typeof config[key] !== 'number' || !Number.isFinite(config[key]) || config[key] < 0) throw new Error(`${key} 必须是非负数字`);
  }
  if (config.price_floor > config.price_ceiling) throw new Error('价格下限不能大于上限');
  if (config.price_ranges !== null) {
    if (!Array.isArray(config.price_ranges) || config.price_ranges.length > 20 || config.price_ranges.some(r => !r || typeof r.min !== 'number' || !Number.isFinite(r.min) || r.min < 0 || (r.max !== null && (typeof r.max !== 'number' || !Number.isFinite(r.max) || r.max < r.min)))) throw new Error('多段价格区间无效');
    config.price_ranges = config.price_ranges.map(r => ({ min: r.min, max: r.max }));
  }
  if (!['sku_min', 'price_band'].includes(config.price_basis)) throw new Error('price_basis 必须为 sku_min 或 price_band');
  if (typeof config.require_new_entry !== 'boolean') throw new Error('require_new_entry 必须是布尔值');
  if (!['全部', '男款', '女款', '中性款'].includes(config.gender)) throw new Error('gender 必须为全部、男款、女款或中性款');
  if (config.timezone !== 'Asia/Shanghai') throw new Error('本工具使用 Asia/Shanghai 时区');
  return config;
}

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const stableText = (value) => String(value ?? '');

const safeHttpUrl = (value) => {
  const raw = stableText(value).trim();
  if (!raw) return '';
  try {
    const url = new URL(raw);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch {
    return '';
  }
};

const domId = (value) => Array.from(stableText(value)).map((c) => c.codePointAt(0).toString(16)).join('-');

export function productPricePresentation(product = {}) {
  const display = stableText(product.price_display).trim();
  const band = stableText(product.price_band_display).trim() || (/^价格带\s*[:：]?/.test(display) ? display : '');
  return band
    ? { label: '价格带', value: band.replace(/^价格带\s*[:：]?\s*/, '') || '待验证', isBand: true }
    : { label: '页面价格', value: display || (product.price_min != null ? `¥${product.price_min}` : '待验证'), isBand: false };
}

export function parseProductPriceBand(product = {}) {
  const presentation = productPricePresentation(product);
  if (!presentation.isBand) return null;
  const amount = '(?:[¥￥]\\s*)?((?:\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.\\d{1,2})?)\\s*(?:元)?';
  const match = presentation.value.match(new RegExp('^' + amount + '(?:\\s*[-–—~～至]\\s*' + amount + ')?$'));
  if (!match) return null;
  const min = Number(match[1].replaceAll(',', '')), max = Number((match[2] || match[1]).replaceAll(',', ''));
  return Number.isFinite(min) && Number.isFinite(max) && min <= max ? { min, max } : null;
}

const rankValue = (entry) => {
  const value = Number(entry?.rank);
  return Number.isInteger(value) && value > 0 ? value : Number.POSITIVE_INFINITY;
};

const publishTimestamp = (entry) => {
  let raw = stableText(entry?.work?.published_at).trim();
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?$/.test(raw)) raw = raw.replace(' ', 'T') + '+08:00';
  const value = Date.parse(raw);
  return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
};

const compareStableId = (left, right) => stableText(left).localeCompare(stableText(right), 'zh-CN', {
  numeric: true,
  sensitivity: 'base',
});

export function sortWorksByRank(works) {
  return Array.from(works ?? []).sort((left, right) => (
    rankValue(left) - rankValue(right)
    || publishTimestamp(right) - publishTimestamp(left)
    || compareStableId(left?.work?.id, right?.work?.id)
  ));
}

export function choosePrimaryWork(works) {
  return sortWorksByRank(works)[0] ?? null;
}

export function repeatTier(count) {
  if (count >= 5) return '高频出现';
  if (count >= 3) return '多作品出现';
  if (count === 2) return '重复出现';
  if (count === 1) return '单次出现';
  return '待验证';
}

export function sortGroupsByRank(groups) {
  return Array.from(groups ?? []).sort((left, right) => (
    rankValue(left.primary_observation ?? left.primary_work) - rankValue(right.primary_observation ?? right.primary_work)
    || (right.repeat_count ?? right.works?.length ?? 0) - (left.repeat_count ?? left.works?.length ?? 0)
    || publishTimestamp(right.primary_observation ?? right.primary_work) - publishTimestamp(left.primary_observation ?? left.primary_work)
    || compareStableId(left?.product?.id, right?.product?.id)
  ));
}

function dateKey(value) {
  const match = stableText(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const key = `${match[1]}-${match[2]}-${match[3]}`;
  const parsed = new Date(`${key}T00:00:00Z`);
  return Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== key ? null : key;
}

function publicationDate(value) {
  const raw = stableText(value).trim();
  if (dateKey(raw)) return raw;
  // Local timestamps are business time. Zoned timestamps are converted before filtering.
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})?$/);
  if (!match || !dateKey(match[1]) || Number(match[2]) > 23 || Number(match[3]) > 59 || Number(match[4] ?? 0) > 59) return null;
  const timestamp = Date.parse(raw.replace(' ', 'T') + (match[5] ? '' : '+08:00'));
  if (!Number.isFinite(timestamp)) return null;
  return new Date(timestamp + 8 * 3600000).toISOString().slice(0, 10);
}

function shiftDate(key, amount) {
  const date = new Date(`${key}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

function numericPrice(value) {
  if ((typeof value !== 'number' && typeof value !== 'string') || (typeof value === 'string' && !value.trim())) return null;
  const parsed = Number(value);
  return typeof value !== 'boolean' && Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function uniqueRelationKey(entry, index) {
  const productId = stableText(entry?.product?.id).trim();
  const workId = stableText(entry?.work?.id).trim();
  return productId && workId ? `${productId}\u0000${workId}` : `__unkeyed__${index}`;
}

export function buildSelectionReport(input, overrides = {}) {
  const sourceType = input?.meta?.source_type ?? 'graphic_ranking';
  if (!['graphic_ranking', 'product_ranking'].includes(sourceType)) throw new Error('不支持的数据来源类型；店铺榜和类目分析不能作为商品榜导入');
  const productMode = sourceType === 'product_ranking';
  const sourceRows = productMode ? input?.products : input?.relations;
  if (!Array.isArray(sourceRows)) throw new Error(productMode ? '商品榜原始输入必须包含 products 数组' : 'relations 必须是数组');
  for (const key of ['coverage', 'failed_nodes', 'expected_nodes']) {
    if (input[key] !== undefined && !Array.isArray(input[key])) throw new Error(`${key} 必须是数组`);
  }
  const config = normalizeConfig({ ...input.config, ...overrides });
  const rankingDate = dateKey(input?.meta?.ranking_date);
  if (!rankingDate) throw new Error('meta.ranking_date must be YYYY-MM-DD');
  const windowStart = shiftDate(rankingDate, 1 - config.publication_days);
  const seen = new Set();
  const deduplicated = [];
  let duplicateRelations = 0;

  for (const [index, source] of sourceRows.entries()) {
    if (!source || typeof source !== 'object' || Array.isArray(source)) throw new Error(`第 ${index + 1} 条关系必须是对象`);
    for (const [label, value] of [['商品ID', source.product?.id], ['作品ID', source.work?.id]]) {
      if (value !== undefined && value !== null && typeof value !== 'string') throw new Error(`第 ${index + 1} 条${label}必须是文本，不能使用可能丢失精度的数字`);
      if (typeof value === 'string' && /^[+-]?\d+(?:\.\d+)?e[+-]?\d+$/i.test(value.trim())) throw new Error(`第 ${index + 1} 条${label}已变成科学计数法，请从原始数据重新按文本导出`);
    }
    if (source.category_path !== undefined && (!Array.isArray(source.category_path) || source.category_path.some((part) => typeof part !== 'string'))) throw new Error(`第 ${index + 1} 条类目路径必须是文本数组`);
    const key = productMode && stableText(source.product?.id).trim()
      ? JSON.stringify([stableText(source.product.id).trim(), source.category_path ?? [], source.source_filters?.price_band ?? 'all'])
      : uniqueRelationKey(source, index);
    if (seen.has(key)) {
      duplicateRelations += 1;
      continue;
    }
    seen.add(key);
    deduplicated.push({ ...structuredClone(source), category_path: source.category_path ?? [] });
  }

  const accepted = [];
  const unresolved = [];
  const summary = {
    source_relations: sourceRows.length,
    duplicate_relations: duplicateRelations,
    price_excluded: 0,
    outside_window: 0,
    not_new: 0,
    gender_excluded: 0,
    unresolved: 0,
    qualified_relations: 0,
    unique_products: 0,
  };

  for (const entry of deduplicated) {
    if (dateKey(entry.ranking_date) !== rankingDate) {
      unresolved.push({ reason: '记录榜单日期缺失或与任务日期不一致', entry });
      continue;
    }
    const publishedDate = productMode ? null : publicationDate(entry?.work?.published_at);
    if (!productMode && !publishedDate) {
      unresolved.push({ reason: '发布时间缺失或无法解析', entry });
      continue;
    }
    if (!productMode && config.require_new_entry && entry?.is_new !== true) {
      if (entry?.is_new === false) summary.not_new += 1;
      else unresolved.push({ reason: '缺少新上榜证据', entry });
      continue;
    }
    if (!productMode && (publishedDate < windowStart || publishedDate > rankingDate)) {
      summary.outside_window += 1;
      continue;
    }
    const priceMin = numericPrice(entry?.product?.price_min);
    const band = config.price_basis === 'price_band' ? parseProductPriceBand(entry?.product) : null;
    const priceRange = band || (priceMin !== null ? { min: priceMin, max: priceMin } : null);
    const requestedRanges = config.price_ranges === null ? [{ min: config.price_floor, max: config.price_ceiling }] : config.price_ranges;
    if (priceRange && requestedRanges.length && !requestedRanges.some(r => priceRange.min <= (r.max ?? Infinity) && priceRange.max >= r.min)) {
      summary.price_excluded += 1;
      continue;
    }
    if (!stableText(entry?.product?.id).trim()) {
      unresolved.push({ reason: '商品ID缺失，无法分组', entry });
      continue;
    }
    if (config.gender !== '全部' && entry.product.apparel?.gender !== config.gender) {
      if (!entry.product.apparel?.gender) unresolved.push({ reason: '款别缺失，无法确认是否符合指定男款/女款', entry });
      else summary.gender_excluded += 1;
      continue;
    }
    entry.product.id = stableText(entry.product.id).trim();
    if (entry.work?.id !== undefined) entry.work.id = stableText(entry.work.id).trim();
    entry.publish_date = publishedDate;
    entry.is_demo = input.meta.is_demo === true;
    entry.price_status = priceMin === null ? '待验证' : '已读取';
    entry.price_filter_basis = band ? 'price_band' : priceMin !== null ? 'sku_min' : 'unknown';
    accepted.push(entry);
  }

  const grouped = new Map();
  for (const entry of accepted) {
    const productId = stableText(entry.product.id);
    if (!grouped.has(productId)) grouped.set(productId, []);
    grouped.get(productId).push(entry);
  }

  const groups = [];
  for (const worksInput of grouped.values()) {
    const works = sortWorksByRank(worksInput);
    const primary = choosePrimaryWork(works);
    const distinctIds = new Set(works.map((item) => stableText(item?.work?.id).trim()).filter(Boolean));
    const repeatCount = distinctIds.size;
    const accounts = new Set(works.map((item) => stableText(item.work?.account).trim()).filter(Boolean));
    groups.push({
      is_product_ranking: productMode,
      product: structuredClone(primary.product),
      category_path: Array.from(primary.category_path ?? []),
      primary_work: productMode ? null : primary,
      primary_observation: productMode ? primary : null,
      observations: productMode ? works : [],
      works: productMode ? [] : works,
      repeat_count: productMode ? null : repeatCount,
      account_count: productMode ? null : accounts.size,
      missing_account_count: productMode ? null : works.filter((item) => !stableText(item.work?.account).trim()).length,
      repeat_tier: productMode ? '商品榜记录' : repeatTier(repeatCount),
      price_status: works.some((item) => item.price_status === '待验证') ? '待验证' : '已读取',
      price_filter_basis: primary.price_filter_basis,
    });
  }

  summary.unresolved = unresolved.length;
  summary.qualified_relations = accepted.length;
  summary.unique_products = groups.length;

  const expected = input.expected_nodes ?? [];
  if (expected.some((path) => !Array.isArray(path) || !path.length || path.some((part) => typeof part !== 'string' || !part.trim()))) throw new Error('expected_nodes 必须包含非空的类目路径数组');
  const coverage = structuredClone(input.coverage ?? []);
  const failures = structuredClone(input.failed_nodes ?? []);
  const nodeKey = (path) => JSON.stringify(path);
  const completed = new Set(coverage.filter((item) => item.status === 'complete' && item.reached_top_200_or_end === true).map((item) => nodeKey(item.category_path)));
  const missing = expected.filter((path) => !completed.has(nodeKey(path)));
  const complete = expected.length > 0 && missing.length === 0 && failures.length === 0 && coverage.every((item) => item.status === 'complete' && item.reached_top_200_or_end === true);

  return {
    meta: {
      ...structuredClone(input.meta ?? {}),
      ranking_date: rankingDate,
      source_type: sourceType,
      publish_window: productMode ? null : [windowStart, rankingDate],
      applied_filters: productMode ? ['price', 'gender'] : ['publication_date', 'new_entry', 'price', 'gender'],
      price_rule: config.price_ranges?.length === 0 ? '不限价格；未知价格保留' : config.price_basis === 'price_band'
        ? `价格带与 ${config.price_ranges === null ? `¥${config.price_floor}–¥${config.price_ceiling}` : config.price_ranges.length ? config.price_ranges.map(r => r.max === null ? `¥${r.min}以上` : `¥${r.min}–¥${r.max}`).join(' 或 ') : '全部价位'} 有交集（含边界）；无价格带用已知最低价；未知保留`
        : `最低可购买价 ¥${config.price_floor}–¥${config.price_ceiling}；缺失保留并标记`,
    },
    config,
    coverage,
    coverage_state: { complete, expected: expected.length, completed: expected.filter((path) => completed.has(nodeKey(path))).length, missing_nodes: missing },
    failed_nodes: failures,
    unresolved,
    summary,
    groups: sortGroupsByRank(groups),
  };
}

function workLink(entry) {
  if (entry?.is_demo === true) return '';
  const id = stableText(entry?.work?.id).trim();
  return id ? `https://www.douyin.com/video/${encodeURIComponent(id)}` : '';
}

function renderMetrics(metrics = {}, includeContent = true) {
  const fields = [
    ['payment_amount' in metrics ? '用户支付金额' : '成交/交易', 'payment_amount' in metrics ? metrics.payment_amount : metrics.transaction_amount],
    ['件数', metrics.sales_count],
  ];
  if ('clicks' in metrics) fields.push(['点击次数', metrics.clicks]);
  if ('click_conversion_rate' in metrics) fields.push(['点击成交转化率', metrics.click_conversion_rate]);
  if (includeContent) fields.push(['观看', metrics.views], ['点赞', metrics.likes]);
  return fields.map(([label, value]) => `<span><b>${escapeHtml(label)}</b>${escapeHtml(value === undefined || value === null || value === '' ? '待验证' : value)}</span>`).join('');
}

function renderWork(entry, expanded = false) {
  const contentLink = workLink(entry);
  const category = (entry.category_path ?? []).join(' / ');
  const search = [entry.work?.title, entry.work?.author, entry.work?.account, entry.work?.id].join(' ').toLowerCase();
  return `<div class="work ${expanded ? 'work-expanded' : ''}" data-publish-date="${escapeHtml(entry.publish_date)}" data-category="${escapeHtml(category)}" data-search="${escapeHtml(search)}">
    <div class="rank-tag">排名 ${escapeHtml(entry.rank ?? '待验证')}</div>
    <div class="work-copy">
      <strong>${escapeHtml(entry.work?.title || '（无标题）')}</strong>
      <span>${escapeHtml(entry.work?.author || '作者待验证')} · ${escapeHtml(entry.work?.account || '账号待验证')} · ${escapeHtml(entry.work?.published_at || '发布时间待验证')}</span>
      <div class="metrics">${renderMetrics(entry.metrics)}</div>
      <small>作品ID：${escapeHtml(entry.work?.id || '待验证')} · ${escapeHtml((entry.category_path ?? []).join(' / '))}</small>
    </div>
    <div class="actions">${contentLink ? `<a href="${escapeHtml(contentLink)}" target="_blank" rel="noopener noreferrer">抖音作品</a>` : '<span class="muted">作品链接待验证</span>'}</div>
  </div>`;
}

function renderGroup(group) {
  const primary = group.primary_observation ?? group.primary_work;
  const productId = stableText(group.product?.id);
  const panelId = `works-${domId(productId)}`;
  const articleId = `product-${domId(productId)}`;
  const entries = group.is_product_ranking ? group.observations : group.works;
  const dates = [...new Set(entries.map((item) => item.publish_date).filter(Boolean))].join(',');
  const categories = [...new Set(entries.map((item) => (item.category_path ?? []).join(' / ')))].join('|');
  const apparel = group.product.apparel ?? {};
  const productSearch = [group.product?.name, productId, group.product?.price_display, ...Object.values(apparel), group.product.shop].join(' ');
  const productLink = safeHttpUrl(group.product?.link);
  const price = productPricePresentation(group.product);
  return `<article class="product" id="${escapeHtml(articleId)}" data-product-id="${escapeHtml(productId)}" data-dates="${escapeHtml(dates)}" data-categories="${escapeHtml(categories)}" data-repeat="${group.repeat_count ?? 0}" data-gender="${escapeHtml(apparel.gender || '待验证')}" data-type="${escapeHtml(apparel.type || '待验证')}" data-fit="${escapeHtml(apparel.fit || '待验证')}" data-product-search="${escapeHtml(productSearch.toLowerCase())}">
    <div class="product-main">
      <div class="rank-tag rank-primary">排名 ${escapeHtml(primary?.rank ?? '待验证')}</div>
      <div class="product-copy">
        <div class="product-heading"><h3>${productLink ? `<a class="product-title" href="${escapeHtml(productLink)}" target="_blank" rel="noopener noreferrer">${escapeHtml(group.product?.name || '商品名称待验证')}</a>` : escapeHtml(group.product?.name || '商品名称待验证')}</h3><span class="repeat repeat-${Math.min(group.repeat_count ?? 0, 5)}">${group.is_product_ranking ? '商品榜候选' : `${escapeHtml(group.repeat_tier)} · ${group.repeat_count}个作品`}</span></div>
        <p>${escapeHtml(price.label)}：${escapeHtml(price.value)}${group.price_status === '待验证' ? ' · 最低可购买价待验证' : ''} · 商品ID ${escapeHtml(productId)} · ${escapeHtml(group.category_path.join(' / '))}</p>
        <p>${[['款别', apparel.gender], ['品类', apparel.type], ['版型', apparel.fit], ['面料', apparel.fabric], ['季节', apparel.season], ['尺码', apparel.sizes], ['价格对应SKU', group.product.price_sku], ['店铺', group.product.shop]].map(([label, value]) => `${label}：${escapeHtml(value || '待验证')}`).join(' · ')}</p>
        ${group.is_product_ranking ? '<p>查询价位：' + escapeHtml(primary?.source_filters?.price_band_label || '不限价格') + '；排名对应该查询条件。未提供作品和推广账号证据，不计算内容重复度。</p>' : `<p>已知推广账号 ${group.account_count} 个${group.missing_account_count ? `（${group.missing_account_count} 条作品账号待验证）` : ''} · 重复出现仅为观察信号</p><p class="primary-title">代表作品：${escapeHtml(group.primary_work?.work?.title || '（无标题）')}</p>`}
        <div class="metrics">${renderMetrics(primary?.metrics, !group.is_product_ranking)}</div>
      </div>
      <div class="actions product-actions">
        ${productLink ? `<a href="${escapeHtml(productLink)}" target="_blank" rel="noopener noreferrer">商品详情</a>` : '<span class="muted">商品链接待验证</span>'}
        ${!group.is_product_ranking && workLink(group.primary_work) ? `<a href="${escapeHtml(workLink(group.primary_work))}" target="_blank" rel="noopener noreferrer">代表作品</a>` : ''}
        <button type="button" class="toggle" aria-expanded="false" aria-controls="${escapeHtml(panelId)}">${group.is_product_ranking ? '榜单记录' : '全部作品'} ${entries.length}</button>
      </div>
    </div>
    <div class="works" id="${escapeHtml(panelId)}" hidden>${entries.map((entry) => group.is_product_ranking ? `<div class="work" data-publish-date="" data-category="${escapeHtml((entry.category_path ?? []).join(' / '))}" data-search=""><div class="rank-tag">排名 ${escapeHtml(entry.rank ?? '待验证')}</div><div class="work-copy"><strong>${escapeHtml((entry.category_path ?? []).join(' / ') || '类目待验证')}</strong><span>榜单日期 ${escapeHtml(entry.ranking_date)}</span><div class="metrics">${renderMetrics(entry.metrics, false)}</div></div></div>` : renderWork(entry, true)).join('')}</div>
  </article>`;
}

function coveragePath(item) {
  return Array.isArray(item?.category_path) ? item.category_path.join(' / ') : stableText(item?.category_path || item?.node || '待验证');
}

function safeJson(value) {
  return JSON.stringify(value).replaceAll('<', '\\u003c').replaceAll('>', '\\u003e').replaceAll('&', '\\u0026');
}

export function renderSelectionHtml(report) {
  const productMode = report.meta.source_type === 'product_ranking';
  const entries = report.groups.flatMap((group) => productMode ? group.observations : group.works);
  const repeated = report.groups.filter((group) => group.repeat_count >= 2);
  const categories = [...new Set(entries.map((entry) => (entry.category_path ?? []).join(' / ')))].filter(Boolean);
  const dates = [...new Set(entries.map((entry) => entry.publish_date).filter(Boolean))].sort().reverse();
  const coverageRows = report.coverage.map((item) => `<tr><td>${escapeHtml(coveragePath(item))}</td><td>${escapeHtml(item.status || '待验证')}</td><td>${escapeHtml(item.attempts ?? '—')}</td><td>${escapeHtml(item.rows ?? item.relations ?? '—')}</td></tr>`).join('');
  const failedRows = report.failed_nodes.map((item) => `<li>${escapeHtml(coveragePath(item))}：${escapeHtml(item.reason || item.status || '读取失败')}</li>`).join('');
  const unresolvedRows = report.unresolved.map((item) => `<li>${escapeHtml(item.reason)} · 商品 ${escapeHtml(item.entry?.product?.id || '待验证')} · 作品 ${escapeHtml(item.entry?.work?.id || '待验证')}</li>`).join('');
  const initialProducts = report.groups.map(renderGroup).join('');
  const radar = repeated.length ? repeated.map((group) => `<a class="radar-item" href="#product-${escapeHtml(domId(group.product.id))}" data-jump-product="${escapeHtml(group.product.id)}"><b>${escapeHtml(group.repeat_tier)}</b><span>${escapeHtml(group.product.name)} · ${group.repeat_count}个作品 · 最佳排名${escapeHtml(group.primary_work.rank)}</span></a>`).join('') : '<p class="muted">本轮暂无重复商品。</p>';
  const apparelFilter = (key, label) => `<select id="${key}-filter" aria-label="${label}"><option value="">全部${label}</option>${[...new Set(report.groups.map((group) => group.product.apparel?.[key] || '待验证'))].sort().map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('')}</select>`;

  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>裤装选品清单 · ${escapeHtml(report.meta.ranking_date)}</title>
<style>
:root{--paper:#F7F8F6;--ink:#17191A;--signal:#F0C62E;--line:#CDD2CF;--muted:#66706B;--white:#FFF;--danger:#9C372E;--display:"Arial Narrow","PingFang SC","Microsoft YaHei",sans-serif;--body:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;--utility:ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 var(--body)}a{color:inherit}.shell{width:min(1480px,calc(100% - 32px));margin:auto}.top{border-bottom:1px solid var(--line);background:var(--white)}.top .shell{display:flex;justify-content:space-between;gap:20px;align-items:end;padding:20px 0}.eyebrow{margin:0 0 4px;font:12px/1.4 var(--utility);letter-spacing:.14em;color:var(--muted)}h1{margin:0;font:800 clamp(24px,3vw,40px)/1.05 var(--display);letter-spacing:.02em}h2{margin:0 0 12px;font:800 18px/1.2 var(--display)}h3{margin:0;font:800 16px/1.3 var(--display)}.meta{text-align:right;color:var(--muted)}.toolbar{position:sticky;top:0;z-index:10;border-bottom:1px solid var(--line);background:rgba(247,248,246,.96)}.toolbar .shell{display:grid;grid-template-columns:minmax(220px,1fr) repeat(3,minmax(140px,auto)) auto;gap:8px;padding:10px 0}.toolbar input,.toolbar select,.toolbar button{min-height:38px;border:1px solid var(--line);border-radius:4px;background:var(--white);color:var(--ink);padding:0 10px;font:inherit}.toolbar button,.actions a,.actions button{cursor:pointer}.summary{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--line);border-right:0;margin:18px 0;background:var(--white)}.stat{padding:14px;border-right:1px solid var(--line)}.stat b{display:block;font:800 25px/1.1 var(--utility)}.stat span{color:var(--muted)}.block{margin:18px 0;border-top:3px solid var(--ink);background:var(--white);padding:16px}.block-head{display:flex;justify-content:space-between;gap:16px;align-items:baseline}.block-head p{margin:0;color:var(--muted)}.radar{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.radar-item{display:flex;flex-direction:column;border:1px solid var(--line);padding:12px;text-decoration:none}.radar-item b{color:#6E5700}.audit-table{width:100%;border-collapse:collapse}.audit-table th,.audit-table td{padding:9px;border-bottom:1px solid var(--line);text-align:left}.audit-table th{font:12px/1.4 var(--utility);color:var(--muted)}.alert{color:var(--danger)}.product-list{border-top:1px solid var(--line)}.product{border-bottom:1px solid var(--line);background:var(--white)}.product-main,.work{display:grid;grid-template-columns:96px minmax(0,1fr) 220px;gap:14px;align-items:start;padding:14px}.rank-tag{display:inline-flex;width:max-content;min-width:74px;justify-content:center;background:var(--signal);padding:5px 8px;font:800 13px/1.4 var(--utility)}.rank-primary{font-size:15px}.product-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.product-copy p{margin:4px 0;color:var(--muted)}.primary-title{color:var(--ink)!important}.repeat{border:1px solid var(--line);padding:2px 6px;font:12px/1.4 var(--utility)}.repeat-2,.repeat-3,.repeat-4,.repeat-5{border-color:var(--signal);background:#FFF8D7}.metrics{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px}.metrics span{color:var(--muted)}.metrics b{color:var(--ink);margin-right:5px}.actions{display:flex;justify-content:flex-end;gap:7px;flex-wrap:wrap}.actions a,.actions button{border:1px solid var(--ink);border-radius:3px;background:var(--white);padding:7px 9px;text-decoration:none;font:inherit}.actions a:hover,.actions button:hover{background:var(--ink);color:var(--white)}:where(a,button,input,select):focus-visible{outline:3px solid var(--signal);outline-offset:2px}.works{border-top:1px dashed var(--line);background:#FBFCFA}.work{grid-template-columns:96px minmax(0,1fr) 130px;padding-left:34px}.work+.work{border-top:1px solid var(--line)}.work-copy{display:flex;flex-direction:column;gap:3px}.work-copy>span,.work-copy small,.muted{color:var(--muted)}.list{margin:8px 0 0;padding-left:20px}.empty{padding:48px 20px;text-align:center;background:var(--white)}.footer{padding:30px 0;color:var(--muted)}[hidden]{display:none!important}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media(max-width:900px){.toolbar .shell{grid-template-columns:1fr 1fr}.summary{grid-template-columns:repeat(2,1fr)}.radar{grid-template-columns:1fr}.product-main,.work{grid-template-columns:86px minmax(0,1fr)}.actions{grid-column:2;justify-content:flex-start}.meta{text-align:left}.top .shell{align-items:start;flex-direction:column}}@media(max-width:560px){.shell{width:min(100% - 20px,1480px)}.toolbar{position:static}.toolbar .shell{grid-template-columns:1fr}.summary{grid-template-columns:repeat(2,1fr)}.summary .stat:last-child{grid-column:1/-1}.product-main,.work{display:flex;flex-direction:column;padding:12px}.actions{justify-content:flex-start}.metrics{gap:7px 12px}}
.toolbar .shell{grid-template-columns: minmax(180px,2fr) repeat(6,minmax(100px,1fr)) auto}.notice{padding:12px 16px;background:#FFF8D7;border-bottom:1px solid var(--line)}@media(max-width:1200px){.toolbar .shell{grid-template-columns:repeat(4,1fr)}}@media(max-width:560px){.toolbar .shell{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
${report.meta.is_demo === true ? '<div class="notice"><b>演示数据</b>：以下商品、账号和成交指标均为虚构示例，不代表真实榜单。</div>' : ''}
<header class="top"><div class="shell"><div><p class="eyebrow">男女裤装 · 候选商品观察</p><h1>${productMode ? '男女裤商品榜选品' : `近${report.config.publication_days}日${report.config.require_new_entry ? '新上榜选品' : '发布作品观察'}`}</h1></div><div class="meta">${escapeHtml(report.meta.ranking_name || (productMode ? '商品榜单' : '图文直接成交榜'))} / ${escapeHtml(report.meta.period || (productMode ? '待核实' : '近1天'))}<br>榜单日 ${escapeHtml(report.meta.ranking_date)}${productMode ? ' · 统计周期以源页面为准' : ` · 发布窗口 ${escapeHtml(report.meta.publish_window[0])}—${escapeHtml(report.meta.publish_window[1])}`}<br>${escapeHtml(report.meta.price_rule)} · 款别 ${escapeHtml(report.config.gender)}</div></div></header>
<div class="toolbar"><div class="shell"><input id="search" type="search" placeholder="搜索商品、作品、作者、账号或ID" aria-label="搜索"><select id="date-filter" aria-label="发布日期" ${productMode ? 'disabled hidden' : ''}><option value="">全部发布日期</option>${dates.map((date) => `<option value="${escapeHtml(date)}">${escapeHtml(date)}</option>`).join('')}</select><select id="category-filter" aria-label="类目"><option value="">全部类目</option>${categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join('')}</select><select id="repeat-filter" aria-label="重复度" ${productMode ? 'disabled hidden' : ''}><option value="">全部重复度</option><option value="2">重复出现及以上</option><option value="3">多作品出现及以上</option><option value="5">高频出现及以上</option></select>${apparelFilter('gender', '款别')}${apparelFilter('type', '品类')}${apparelFilter('fit', '版型')}<button id="clear" type="button">清除筛选</button></div></div>
${report.meta.collection_scope ? `<div class="notice">${escapeHtml(report.meta.collection_scope)}</div>` : ''}
<main class="shell">
<section class="summary" aria-label="本轮汇总"><div class="stat"><b>${report.summary.unique_products}</b><span>入选商品</span></div><div class="stat"><b>${report.summary.qualified_relations}</b><span>${productMode ? '商品榜记录' : '作品—商品关系'}</span></div><div class="stat"><b>${productMode ? report.summary.source_relations : repeated.length}</b><span>${productMode ? '原始记录' : '重复商品'}</span></div><div class="stat"><b>${report.summary.price_excluded}</b><span>价格排除</span></div><div class="stat"><b>${report.summary.unresolved}</b><span>待核记录</span></div></section>
<section class="block" ${productMode ? 'hidden' : ''}><div class="block-head"><h2>重复商品观察</h2><p>仅统计本轮${report.config.publication_days}日窗口内不同作品ID，不代表盈利或爆款</p></div><div class="radar">${radar}</div></section>
<section class="block"><div class="block-head"><h2>覆盖稽核</h2><p>${report.coverage_state.complete ? '覆盖完整（仅限声明的计划节点与采集范围）' : '覆盖未证实或不完整，不得宣称全量'}</p></div><p>计划节点 ${report.coverage_state.expected || '未提供'} · 已证实完成 ${report.coverage_state.completed}</p><table class="audit-table"><thead><tr><th>类目节点</th><th>状态</th><th>尝试</th><th>关系数</th></tr></thead><tbody>${coverageRows || '<tr><td colspan="4" class="muted">未提供覆盖台账</td></tr>'}</tbody></table>${report.coverage_state.missing_nodes.length ? `<h3 class="alert">未证实完成的节点</h3><ul>${report.coverage_state.missing_nodes.map((path) => `<li>${escapeHtml(path.join(' / '))}</li>`).join('')}</ul>` : ''}${failedRows ? `<h3 class="alert">失败节点</h3><ul class="list alert">${failedRows}</ul>` : ''}${unresolvedRows ? `<h3>待核记录</h3><ul class="list">${unresolvedRows}</ul>` : ''}</section>
<section class="block"><div class="block-head"><h2>完整产品清单</h2><p id="visible-count">${report.groups.length}个商品，按最佳榜单排名升序</p></div><div id="product-list" class="product-list">${initialProducts}</div><div id="empty" class="empty" hidden><p>没有符合当前筛选的商品。</p><button id="empty-clear" type="button">清除筛选</button></div></section>
</main><footer class="footer shell">${productMode ? '本页为商品榜候选清单；商品链接不执行有效性检查。' : '本页为单文件交付；作品链接由作品ID确定性生成，不执行有效性检查。'}</footer>
<script id="selection-data" type="application/json">${safeJson(report)}</script>
<script>
(()=>{const list=document.getElementById('product-list');const controls={search:document.getElementById('search'),date:document.getElementById('date-filter'),category:document.getElementById('category-filter'),repeat:document.getElementById('repeat-filter'),gender:document.getElementById('gender-filter'),type:document.getElementById('type-filter'),fit:document.getElementById('fit-filter')};function apply(){const q=controls.search.value.trim().toLowerCase();const d=controls.date.value;const c=controls.category.value;const r=Number(controls.repeat.value||0);let visible=0;list.querySelectorAll('.product').forEach(product=>{const productMatch=!q||product.dataset.productSearch.includes(q);let visibleWorks=0;product.querySelectorAll('.work').forEach(work=>{const workMatch=(!d||work.dataset.publishDate===d)&&(!c||work.dataset.category===c)&&(!q||productMatch||work.dataset.search.includes(q));work.hidden=!workMatch;if(workMatch)visibleWorks+=1});const ok=visibleWorks>0&&(!r||Number(product.dataset.repeat)>=r)&&['gender','type','fit'].every(key=>!controls[key].value||product.dataset[key]===controls[key].value);product.hidden=!ok;if(ok)visible+=1});document.getElementById('visible-count').textContent=visible+'个商品，按最佳榜单排名升序';document.getElementById('empty').hidden=visible!==0}function clear(){Object.values(controls).forEach(control=>control.value='');apply()}Object.values(controls).forEach(control=>control.addEventListener('input',apply));document.getElementById('clear').addEventListener('click',clear);document.getElementById('empty-clear').addEventListener('click',clear);list.addEventListener('click',event=>{const button=event.target.closest('.toggle');if(!button)return;const panel=document.getElementById(button.getAttribute('aria-controls'));const expanded=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!expanded));panel.hidden=expanded});document.querySelectorAll('[data-jump-product]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();const product=list.querySelector('[data-product-id="'+CSS.escape(link.dataset.jumpProduct)+'"]');if(product){clear();product.scrollIntoView({behavior:'smooth',block:'center'})}}));})();
</script>
</body></html>`;
}
