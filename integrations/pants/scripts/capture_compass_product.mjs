// Pass this function's source to the connected browser's evaluate tool.
// Reads rendered business DOM only; never accesses requests, cookies or framework state.
export function captureCompassProductPage() {
  const visible = (element) => element && element.getClientRects().length > 0;
  if (location.hostname !== 'compass.jinritemai.com' || location.pathname !== '/shop/chance/rank-product') {
    throw new Error('当前页面不是罗盘商品榜单');
  }
  const table = Array.from(document.querySelectorAll('table')).find(visible);
  const category = Array.from(document.querySelectorAll('div.aurora-cascader')).find(visible);
  const identity = Array.from(document.querySelectorAll('[class^="userName-"]')).find(visible);
  if (!table || !category || !identity?.innerText.trim()) throw new Error('账号、类目或榜单表格未就绪');
  const dates = document.body.innerText.match(/\d{4}\/\d{2}\/\d{2}/g) ?? [];
  const tabs = Array.from(document.querySelectorAll('[role="tab"][aria-selected="true"]')).map(el => el.innerText.trim());
  const headers = Array.from(table.querySelectorAll('th')).map(el => el.innerText.trim());
  const rows = Array.from(table.querySelectorAll('tbody tr[data-row-key]')).filter(visible).map(row => {
    const cells = Array.from(row.querySelectorAll('td'));
    const title = cells[1]?.querySelector('[class^="name-"]');
    const titleAnchor = title?.closest('a[href]') ?? title?.querySelector('a[href]');
    return {
      row_key: row.getAttribute('data-row-key'),
      cells: cells.map(cell => cell.innerText.trim()),
      rank_text: cells[0]?.querySelector('[class^="rank-"]')?.innerText.trim() ?? '',
      product_name: title?.innerText.trim() ?? '',
      price_band: cells[1]?.querySelector('[class^="price-"]')?.innerText.trim() ?? '',
      shop_name: cells[2]?.querySelector('[class^="shop-"] [class^="name-"]')?.innerText.trim() ?? '',
      product_link: titleAnchor?.href ?? cells[1]?.querySelector('a[href]')?.href ?? '',
      title_element_tag: title?.tagName ?? '',
      title_role: title?.getAttribute('role') ?? '',
      title_link_requires_click: !titleAnchor?.href,
      details_available: Array.from(cells[7]?.querySelectorAll('button') ?? []).some(button => button.innerText.trim() === '查看详情' && !button.disabled),
    };
  });
  const emptyText = rows.length ? '' : (table.innerText.match(/暂无(?:相关)?(?:数据|商品|搜索结果)/)?.[0] || '');
  if (!rows.length && !emptyText) throw new Error('没有稳定商品行；不能把读取失败当作零商品');
  const totalText = Array.from(document.querySelectorAll('li')).find(el => visible(el) && /^共\d+条$/.test(el.innerText.trim()))?.innerText.trim() ?? '';
  const activePage = Array.from(document.querySelectorAll('li')).find(el => visible(el) && String(el.className).includes('pagination-item-active'))?.innerText.trim() ?? '';
  const parts = category.innerText.split('/').map(part => part.trim());
  // The fourth-level leaf itself can contain a slash, e.g. 鲨鱼裤/打底裤.
  const categoryPath = parts.length > 4 ? [...parts.slice(0, 3), parts.slice(3).join('/')] : parts;
  return {
    schema: 'compass-product-dom-v1', source_url: location.origin + location.pathname,
    observed_identity: identity.innerText.trim(), category_path: categoryPath,
    selected_tabs: tabs, dates, total_text: totalText, page_number: /^\d+$/.test(activePage) ? Number(activePage) : null,
    headers, rows, captured_at: new Date().toISOString(),
    ...(emptyText ? { empty_state_text: emptyText } : {}),
  };
}
