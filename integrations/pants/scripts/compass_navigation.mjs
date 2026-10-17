// Invoked by the desktop host against the visible Compass UI. No network APIs.
export function compassPageAction(action, value) {
  const visible = el => el && el.getClientRects().length > 0;
  const text = el => el?.innerText?.trim() || '';
  const elements = selector => Array.from(document.querySelectorAll(selector)).filter(visible);
  const click = el => { if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true' || /(?:^|\s)\S*disabled/.test(String(el.className))) return false; el.click(); return true; };
  const normalizePrice = label => label.replace(/[¥￥元\s]/g, '').replace(/[–—−~～至]/g, '-');
  const priceLabel = query => ({ all: '不限', '0-50': '0-50', '50-70': '50-70', '70-99': '70-99', '99-150': '99-150', '150+': '150以上' })[query];
  const filterGroup = name => {
    const label = elements('div,span').find(el => text(el).replace(/\s*[:：]\s*$/, '') === name);
    let group = label?.parentElement;
    while (group && text(group).replace(/\s*[:：]\s*$/, '') === name) group = group.parentElement;
    return group;
  };
  const priceGroup = () => filterGroup('价格带');
  const selectedPrice = () => Array.from(priceGroup()?.querySelectorAll('[aria-pressed="true"],[aria-selected="true"],[class*="activeItem-"]') || []).filter(visible).map(text);
  const priceDialog = () => elements('[class*="modal-container"],[role="dialog"]').find(el => Array.from(el.querySelectorAll('input')).some(input => visible(input) && input.getAttribute('placeholder') === '输入最小值') && Array.from(el.querySelectorAll('input')).some(input => visible(input) && input.getAttribute('placeholder') === '输入最大值'));
  const customValues = () => value === '150+' ? ['150', ''] : value.split('-');
  const filterOption = (name, expected) => {
    // Never climb into another filter row: its “不限” belongs to a different setting.
    return Array.from(filterGroup(name)?.querySelectorAll('div,span,button') || []).filter(visible).reverse().find(el => normalizePrice(text(el)) === expected) || null;
  };
  if (action === 'price') {
    if (!priceLabel(value)) throw new Error('无效的价位查询：' + value);
    // Category changes temporarily leave only the custom tag while bands load.
    if (!priceGroup() || !filterOption('价格带', '不限')) return { pending: true };
    if (click(filterOption('价格带', priceLabel(value)))) return { price_band: value, custom: false };
    if (value !== 'all' && click(filterOption('价格带', '自定义'))) return { price_band: value, custom: true };
    throw new Error('罗盘当前类目没有可用价位或自定义入口：' + value);
  }
  if (action === 'price-custom-fill' || action === 'price-custom-confirm' || action === 'price-custom-verify') {
    if (!priceLabel(value) || value === 'all') throw new Error('无效的自定义价位');
    const dialog = priceDialog();
    if (!dialog) return { pending: true };
    const inputs = ['输入最小值', '输入最大值'].map(placeholder => Array.from(dialog.querySelectorAll('input')).find(el => visible(el) && el.getAttribute('placeholder') === placeholder));
    const expected = customValues();
    if (action === 'price-custom-fill') {
      inputs.forEach((input, index) => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, expected[index]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.blur();
      });
      return { filled: true };
    }
    if (inputs.some((input, index) => input.value !== expected[index])) throw new Error('罗盘自定义价位未正确填写：' + value);
    const caption = action === 'price-custom-confirm' ? '确定' : '取消';
    if (!click(Array.from(dialog.querySelectorAll('button')).filter(visible).find(el => text(el) === caption))) throw new Error('罗盘价位弹窗无法' + caption);
    return { verified: true };
  }
  if (action === 'price-custom-reopen') {
    if (priceDialog()) return { pending: true };
    if (!selectedPrice().some(label => normalizePrice(label) === '自定义')) return { pending: true };
    if (!click(filterOption('价格带', '自定义'))) throw new Error('无法核实罗盘自定义价位');
    return { opened: true };
  }
  if (action === 'price-state') {
    return { applied: !priceDialog() && selectedPrice().some(label => normalizePrice(label) === (value.custom ? '自定义' : priceLabel(value.query))) };
  }
  if (action === 'ready') return { ready: Boolean(elements('div.aurora-cascader [role="combobox"]').length && elements('[class^="userName-"]').length && elements('table').length && filterOption('价格带', '不限') && filterOption('品牌类型', '不限')), loading: elements('[aria-busy="true"], [role="progressbar"], [class*="spin-spinning"], [class*="table-loading"]').length > 0 };
  if (action === 'tab') {
    const tab = elements('[role="tab"]').find(el => text(el) === value);
    if (!tab) throw new Error('未找到榜单选项：' + value);
    if (tab.getAttribute('aria-selected') !== 'true') click(tab);
    return { clicked: true };
  }
  if (action === 'reset-filters') {
    const input = elements('input').find(el => (el.getAttribute('placeholder') || '').includes('可搜索所选条件下的商品名'));
    if (input?.value) {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
      input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true }));
    }
    for (const name of ['品牌类型', '价格带']) {
      if (!click(filterOption(name, '不限'))) throw new Error('无法核实筛选项：' + name + '，请打开商品榜后重试');
    }
    return { reset: true };
  }
  if (action === 'category-open') {
    const combo = elements('div.aurora-cascader [role="combobox"]')[0];
    if (!combo) throw new Error('未找到行业类目选择器');
    if (combo.getAttribute('aria-expanded') !== 'true') {
      combo.focus(); combo.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }));
    }
    return { opened: true };
  }
  if (action === 'category-item') return { clicked: click(elements('[role="menuitemcheckbox"], [role="menuitem"]').find(el => text(el) === value)) };
  if (action === 'category-children') {
    const items = elements('[role="menuitemcheckbox"], [role="menuitem"]');
    const parent = items.at(-1)?.parentElement;
    return { names: [...new Set(items.filter(el => el.parentElement === parent).map(text))].filter(name => name && !['全部', '服饰内衣', '服装', '男装', '女装'].includes(name)) };
  }
  if (action === 'first-page') {
    const active = elements('li[class*="pagination-item-active"]')[0];
    if (text(active) === '1') return { clicked: true };
    if (!active && elements('table').some(el => /暂无(?:相关)?(?:数据|商品|搜索结果)/.test(text(el)))) return { clicked: true };
    return { clicked: click(elements('li[class*="pagination-item"]').find(el => text(el) === '1')) };
  }
  if (action === 'next-page') {
    const next = elements('li,button,a').find(el => String(el.className).includes('pagination-next') || /^(下一页|Next page)$/i.test(el.getAttribute('aria-label') || el.getAttribute('title') || text(el)));
    if (!next) throw new Error('未找到下一页入口；不能把读取失败当成榜单结束');
    const disabled = next.disabled || next.getAttribute('aria-disabled') === 'true' || String(next.className).includes('disabled') || next.querySelector('button:disabled');
    if (disabled) return { end: true };
    if (!click(next)) throw new Error('下一页暂时不可点击');
    return { end: false };
  }
  throw new Error('未知页面操作');
}
