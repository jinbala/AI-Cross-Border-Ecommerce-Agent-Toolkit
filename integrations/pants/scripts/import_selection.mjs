export const CSV_HEADERS = ['榜单日期', '类目路径', '排名', '新上榜', '商品ID', '商品名称', '最低价', '价格展示', '价格对应SKU', '商品链接', '店铺', '款别', '品类', '版型', '面料', '季节', '尺码', '作品ID', '作品标题', '作者', '账号', '发布时间', '成交金额', '成交件数', '观看', '点赞'];
export const PRODUCT_CSV_HEADERS = CSV_HEADERS.filter((name) => !['新上榜', '作品ID', '作品标题', '作者', '账号', '发布时间', '观看', '点赞'].includes(name));

export function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', quoted = false, afterQuote = false;
  const source = String(text).replace(/^\uFEFF/, '');
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') { cell += '"'; i += 1; }
      else if (char === '"') { quoted = false; afterQuote = true; }
      else cell += char;
    } else if (char === ',' || char === '\r' || char === '\n') {
      row.push(cell); cell = ''; afterQuote = false;
      if (char !== ',') {
        if (row.some((value) => value.trim())) rows.push(row);
        row = [];
        if (char === '\r' && source[i + 1] === '\n') i += 1;
      }
    } else if (afterQuote) {
      throw new Error('CSV 引号结束后必须是逗号或换行');
    } else if (char === '"') {
      if (cell !== '') throw new Error('CSV 引号必须位于字段开头');
      quoted = true;
    } else cell += char;
  }
  if (quoted) throw new Error('CSV 存在未闭合的引号');
  row.push(cell);
  if (row.some((value) => value.trim())) rows.push(row);
  return rows;
}

export function importCsv(text, rankingDate, sourceType = 'graphic_ranking') {
  if (!['graphic_ranking', 'product_ranking'].includes(sourceType)) throw new Error('不支持的榜单类型');
  const productMode = sourceType === 'product_ranking';
  const [header, ...rows] = parseCsv(text);
  if (!header) throw new Error('CSV 是空文件');
  const names = header.map((value) => value.trim());
  if (new Set(names).size !== names.length) throw new Error('CSV 表头不能重复');
  for (const name of productMode ? ['榜单日期', '商品ID', '商品名称'] : ['榜单日期', '商品ID', '作品ID', '发布时间', '新上榜']) {
    if (!names.includes(name)) throw new Error(`缺少表头：${name}，请使用本工具的 CSV 模板`);
  }
  const objects = rows.map((values, index) => {
    if (values.length !== names.length) throw new Error(`第 ${index + 2} 行列数与表头不同`);
    return Object.fromEntries(names.map((name, i) => [name, values[i].trim()]));
  });
  const dates = [...new Set(objects.map((item) => item['榜单日期']).filter(Boolean))];
  const resolvedDate = rankingDate || (dates.length === 1 ? dates[0] : '');
  if (!resolvedDate) throw new Error('请指定榜单日期；不能将多期榜单直接混在同一次任务中');
  const relations = objects.map((item, index) => {
    const flag = (item['新上榜'] || '').toLowerCase();
    const isNew = ['true', '是', '1'].includes(flag) ? true : ['false', '否', '0'].includes(flag) ? false : null;
    if (flag && isNew === null && flag !== '待验证') throw new Error(`第 ${index + 2} 行新上榜请填写 true/false/是/否，缺失留空`);
    const rawPrice = item['最低价'] ?? '';
    if (rawPrice && !/^\d+(\.\d+)?$/.test(rawPrice)) throw new Error(`第 ${index + 2} 行最低价请填写数字，价格区间请拆出下限；未知留空`);
    const apparel = Object.fromEntries([['gender', '款别'], ['type', '品类'], ['fit', '版型'], ['fabric', '面料'], ['season', '季节'], ['sizes', '尺码']].map(([key, name]) => [key, item[name] || '']));
    if (apparel.gender && !['男款', '女款', '中性款'].includes(apparel.gender)) throw new Error(`第 ${index + 2} 行款别请填男款/女款/中性款，未知留空`);
    return {
      ranking_date: item['榜单日期'], category_path: (item['类目路径'] || '').split('>').map((value) => value.trim()).filter(Boolean),
      rank: /^\d+$/.test(item['排名'] || '') && Number(item['排名']) > 0 ? Number(item['排名']) : null, is_new: isNew,
      product: { id: item['商品ID'], name: item['商品名称'], price_min: rawPrice ? Number(rawPrice) : null, price_display: item['价格展示'] || (rawPrice ? `¥${rawPrice}` : ''), price_sku: item['价格对应SKU'], link: item['商品链接'], shop: item['店铺'], apparel },
      work: { id: item['作品ID'], title: item['作品标题'], author: item['作者'], account: item['账号'], published_at: item['发布时间'] },
      metrics: { transaction_amount: item['成交金额'], sales_count: item['成交件数'], views: item['观看'], likes: item['点赞'] },
    };
  });
  if (productMode) {
    return { meta: { ranking_date: resolvedDate, source: '手动导入 CSV', source_type: sourceType, ranking_name: '商品榜单', period: '待核实', is_demo: false }, coverage: [], failed_nodes: [], products: relations.map(({ work, is_new, ...entry }) => entry) };
  }
  return { meta: { ranking_date: resolvedDate, source: '手动导入 CSV', source_type: sourceType, is_demo: false }, coverage: [], failed_nodes: [], relations };
}
