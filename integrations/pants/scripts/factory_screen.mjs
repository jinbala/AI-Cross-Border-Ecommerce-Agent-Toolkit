// Conservative comparisons use the displayed lower bound, never a midpoint
// or a projection to monthly sales. Unknown and ambiguous values stay unknown.
export function observedRange(raw, percent = false) {
  if (typeof raw !== 'string' && typeof raw !== 'number') return null;
  const value = String(raw).replace(/[\s,，]/g, '').replace(/[–—~～至]/g, '-');
  const match = value.match(/^(\d+(?:\.\d+)?)(万|亿)?(%?)(?:-(\d+(?:\.\d+)?)(万|亿)?(%?))?$/);
  if (!match || (!percent && (match[3] || match[6])) || (percent && !match[3] && !match[6]) || (match[4] && match[2] && !match[5])) return null;
  const scale = unit => unit === '万' ? 10000 : unit === '亿' ? 100000000 : 1;
  const lower = Number(match[1]) * scale(match[2] || (match[4] ? match[5] : ''));
  const upper = match[4] ? Number(match[4]) * scale(match[5] || match[2]) : lower;
  if (!Number.isFinite(lower) || !Number.isFinite(upper) || upper < lower || (percent && (upper > 100 || match[2] || match[5]))) return null;
  return {lower, upper};
}

export function factoryScreen(group, preferences = {}) {
  const metrics = group.primary_observation?.metrics || {};
  const sales = observedRange(metrics.sales_count), conversion = observedRange(metrics.click_conversion_rate, true);
  const minSales = Number(preferences.minSales), minConversion = Number(preferences.minConversion);
  if (!Number.isFinite(minSales) || minSales < 0 || !Number.isFinite(minConversion) || minConversion < 0 || minConversion > 100) throw new Error('成交件数需为非负数，转化率需在 0—100% 之间');
  const keywords = String(preferences.keywords || '').split(/[,，、;；\s]+/).filter(Boolean);
  const text = [group.product.name, ...Object.values(group.product.apparel || {})].join(' ').toLowerCase();
  const matched = keywords.filter(word => text.includes(word.toLowerCase()));
  const keywordPass = !keywords.length || matched.length > 0;
  const needsSales = minSales > 0, needsConversion = minConversion > 0;
  const missing = (needsSales && !sales) || (needsConversion && !conversion);
  const qualifies = keywordPass && !missing && (!needsSales || sales.lower >= minSales) && (!needsConversion || conversion.lower >= minConversion);
  const reasons = [];
  if (needsSales) reasons.push(sales ? `成交下限 ${sales.lower.toLocaleString('zh-CN')} 件${sales.lower >= minSales ? '，达标' : '，低于设定值'}` : '成交件数待核实');
  if (needsConversion) reasons.push(conversion ? `转化下限 ${conversion.lower}%${conversion.lower >= minConversion ? '，达标' : '，低于设定值'}` : '转化率待核实');
  if (keywords.length) reasons.push(matched.length ? '匹配擅长款：'+matched.join('、') : '未匹配擅长款关键词');
  return {qualifies, missing:Boolean(missing), active:needsSales || needsConversion || keywords.length > 0, label:qualifies ? '条件匹配 · 可继续核算' : missing ? '资料不足 · 待核实' : '先观察', reasons};
}
