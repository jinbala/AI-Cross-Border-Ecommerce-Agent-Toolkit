export const COMPASS_PRICE_BANDS = Object.freeze([
  { id: '0-50', label: '0–50 元', min: 0, max: 50 },
  { id: '50-70', label: '50–70 元', min: 50, max: 70 },
  { id: '70-99', label: '70–99 元', min: 70, max: 99 },
  { id: '99-150', label: '99–150 元', min: 99, max: 150 },
  { id: '150+', label: '150 元以上', min: 150, max: null },
]);

export function normalizePriceRanges(ranges) {
  if (!Array.isArray(ranges) || ranges.length > 20) throw new Error('最多选择 20 段价格区间');
  return ranges.map(range => {
    if (!range || typeof range.min !== 'number' || !Number.isFinite(range.min) || range.min < 0 || (range.max !== null && (typeof range.max !== 'number' || !Number.isFinite(range.max) || range.max < range.min))) throw new Error('价格区间须为非负数字，上限不能小于下限');
    return { min: range.min, max: range.max };
  });
}

export function priceRangesLabel(ranges) {
  return ranges.length ? ranges.map(r => r.max === null ? `¥${r.min}以上` : `¥${r.min}–¥${r.max}`).join(' 或 ') : '不限价格';
}

export function parseCustomPriceRanges(value) {
  if (!String(value).trim()) return [];
  const ranges = String(value).split(/[;；\n]+/).map(part => {
    const text = part.trim().replace(/[¥￥元\s]/g, '');
    const match = text.match(/^(\d+(?:\.\d+)?)(?:[-–—~～至](\d+(?:\.\d+)?))$/);
    const open = text.match(/^(\d+(?:\.\d+)?)以上$/);
    if (!match && !open) throw new Error('自定义区间示例：80-120；180-250。多段用分号隔开');
    return { min: Number((match || open)[1]), max: match ? Number(match[2]) : null };
  });
  return normalizePriceRanges(ranges);
}

// Map arbitrary ranges to stable client query bands. The desktop uses a matching
// category preset or the official custom-price dialog, then filters locally.
export function compassQueriesForRanges(ranges) {
  const normalized = normalizePriceRanges(ranges);
  if (!normalized.length) return ['all'];
  return COMPASS_PRICE_BANDS.filter(band => normalized.some(range => band.min <= (range.max ?? Infinity) && (band.max ?? Infinity) >= range.min)).map(band => band.id);
}
