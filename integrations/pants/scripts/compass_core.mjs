const HEADERS = ['排名', '商品', '店铺名称', '用户支付金额', '点击次数', '成交件数', '点击成交转化率', '操作'];
const PANTS = {
  男装: ['短裤', '牛仔裤', '休闲裤', '其他裤子', '西裤', '皮裤', '羽绒裤', '棉裤'],
  女装: ['西裤', '短裤', '其他裤子', '休闲裤', '牛仔裤', '鲨鱼裤/打底裤'],
};
const cleanDisplay = value => String(value ?? '').replace(/\s+/g, ' ').replace(/\s*-\s*/g, '–').trim();

function sourceDate(value) {
  if (!/^\d{4}\/\d{2}\/\d{2}$/.test(value ?? '')) throw new Error('源页面统计日期缺失或格式变化');
  const key = value.replaceAll('/', '-');
  const date = new Date(key + 'T00:00:00Z');
  if (Number.isNaN(date.valueOf()) || date.toISOString().slice(0, 10) !== key) throw new Error('源页面统计日期无效');
  return key;
}

export function normalizeCompassSnapshots(snapshots, expectedIdentity, options = {}) {
  if (!Array.isArray(snapshots) || !snapshots.length) throw new Error('至少需要一份当前页采集快照');
  const products = [], coverage = [], expectedNodes = [];
  let context = null;
  for (const snapshot of snapshots) {
    if (snapshot?.schema !== 'compass-product-dom-v1' || snapshot.source_url !== 'https://compass.jinritemai.com/shop/chance/rank-product') throw new Error('不是受支持的商品榜页面快照');
    if (!snapshot.observed_identity || (expectedIdentity && snapshot.observed_identity !== expectedIdentity)) throw new Error('实际账号身份与预期不一致');
    if (JSON.stringify(snapshot.headers) !== JSON.stringify(HEADERS)) throw new Error('商品榜表头发生变化，请重新核实字段映射');
    if (!Array.isArray(snapshot.category_path) || snapshot.category_path.length !== 4 || snapshot.category_path.some(part => typeof part !== 'string' || !part.trim())) throw new Error('裤装类目路径不完整');
    const apparel = options.allowApparel === true && ['男装', '女装'].includes(snapshot.category_path[2]) && snapshot.category_path[3] !== '全部';
    if (snapshot.category_path[0] !== '服饰内衣' || snapshot.category_path[1] !== '服装' || (!apparel && !PANTS[snapshot.category_path[2]]?.includes(snapshot.category_path[3]))) throw new Error('当前页不是已核实的男女裤类目');
    if (!Array.isArray(snapshot.dates) || snapshot.dates.length !== 2 || !Array.isArray(snapshot.selected_tabs) || snapshot.selected_tabs.length !== 2 || snapshot.selected_tabs[0] !== '总榜') throw new Error('榜单或统计周期未核实');
    const start = sourceDate(snapshot.dates[0]), end = sourceDate(snapshot.dates[1]);
    if (start > end) throw new Error('统计日期范围无效');
    const current = { identity: snapshot.observed_identity, start, end, period: snapshot.selected_tabs[1] };
    if (context && JSON.stringify(current) !== JSON.stringify(context)) throw new Error('不能合并不同账号、榜单或统计周期的快照');
    context = current;
    const explicitEmpty = Array.isArray(snapshot.rows) && snapshot.rows.length === 0 && /^暂无(?:相关)?(?:数据|商品|搜索结果)$/.test(snapshot.empty_state_text || '');
    if (!Array.isArray(snapshot.rows) || (!explicitEmpty && (!Number.isInteger(snapshot.page_number) || snapshot.page_number < 1 || !snapshot.rows.length))) throw new Error('页码或商品行没有读取成功');
    if (!/^共\d+条$/.test(snapshot.total_text ?? '') && !explicitEmpty) throw new Error('未读取到平台总条数');
    if (explicitEmpty && snapshot.total_text && snapshot.total_text !== '共0条') throw new Error('空榜提示与总条数不一致');
    for (const row of snapshot.rows) {
      const key = String(row.row_key ?? '').match(/^(\d+)_(\d+)$/);
      if (!key || row.cells?.length !== HEADERS.length || !row.product_name || !row.shop_name) throw new Error('商品行结构变化，不能可靠读取商品ID、名称或店铺');
      const rank = Number(key[2]);
      if (!Number.isInteger(rank) || rank < 1 || (row.rank_text && Number(row.rank_text) !== rank)) throw new Error('来源行标识与显示排名不一致');
      products.push({
        ranking_date: end, category_path: [...snapshot.category_path], rank,
        ...(snapshot.source_filters ? { source_filters: structuredClone(snapshot.source_filters) } : {}),
        product: {
          id: key[1], id_evidence: '来源表格 data-row-key 的商品部分', name: row.product_name,
          price_display: cleanDisplay(row.price_band), price_band_display: cleanDisplay(row.price_band),
          price_min: null, price_sku: '', shop: row.shop_name, link: row.product_link || '',
          apparel: { gender: snapshot.category_path[2] === '女装' ? '女款' : '男款', type: snapshot.category_path[3] },
        },
        metrics: { payment_amount: cleanDisplay(row.cells[3]), clicks: cleanDisplay(row.cells[4]), sales_count: cleanDisplay(row.cells[5]), click_conversion_rate: cleanDisplay(row.cells[6]) },
        source_evidence: { row_key: row.row_key, rank_cell_text: row.cells[0], page_number: snapshot.page_number, details_available: row.details_available === true },
      });
    }
    const priceScope = snapshot.source_filters?.price_band || 'all';
    const existing = coverage.find(item => JSON.stringify(item.category_path) === JSON.stringify(snapshot.category_path) && (item.price_band || 'all') === priceScope);
    if (existing) {
      if (existing.page_numbers.includes(snapshot.page_number) || (explicitEmpty && existing.rows === 0)) throw new Error('同一类目页码重复；请不要重复合并同页');
      existing.rows += snapshot.rows.length; existing.pages += 1; existing.page_numbers.push(snapshot.page_number);
    } else {
      if (!expectedNodes.some(path => JSON.stringify(path) === JSON.stringify(snapshot.category_path))) expectedNodes.push([...snapshot.category_path]);
      coverage.push({ category_path: [...snapshot.category_path], ...(priceScope !== 'all' ? { price_band: priceScope } : {}), status: 'partial', attempts: 1, pages: explicitEmpty ? 0 : 1, page_numbers: explicitEmpty ? [] : [snapshot.page_number], rows: snapshot.rows.length, source_total: explicitEmpty ? 0 : Number(snapshot.total_text.match(/\d+/)[0]), reached_top_200_or_end: false, failure_reason: explicitEmpty ? '平台明确显示空榜，仅限当前查询条件' : '仅保存指定页，不代表完整榜单' });
    }
  }
  return {
    meta: { source_type: 'product_ranking', source_url: snapshots[0].source_url, observed_identity: context.identity, ranking_name: '商品榜单 / 总榜', ranking_date: context.end, period: `${context.period}（${context.start}—${context.end}）`, period_start: context.start, period_end: context.end, is_demo: false, collection_scope: '真实页面采集，仅限已保存页；价格带不等于已核实SKU最低可购买价', generated_at: new Date().toISOString() },
    expected_nodes: expectedNodes, coverage, failed_nodes: [], products,
  };
}

// Replace a reread page; start a separate collection when account or period changes.
// Both inputs and the result go through the same strict source contract as the CLI.
export function mergeCompassSnapshot(previous, snapshot, options = {}) {
  const nextData = normalizeCompassSnapshots([snapshot], undefined, options);
  if (!Array.isArray(previous)) throw new Error('已保存的采集页格式无效');
  const oldData = previous.length ? normalizeCompassSnapshots(previous, undefined, options) : null;
  const sameContext = oldData && ['observed_identity', 'period_start', 'period_end', 'period'].every(key => oldData.meta[key] === nextData.meta[key]);
  const remaining = sameContext ? previous.filter(item => !(item.page_number === snapshot.page_number && JSON.stringify(item.category_path) === JSON.stringify(snapshot.category_path) && (item.source_filters?.price_band || 'all') === (snapshot.source_filters?.price_band || 'all'))) : [];
  const snapshots = structuredClone([...remaining, snapshot]);
  return { snapshots, data: normalizeCompassSnapshots(snapshots, undefined, options), replaced_context: Boolean(oldData && !sameContext) };
}
