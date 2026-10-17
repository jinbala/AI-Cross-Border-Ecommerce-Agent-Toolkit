import assert from 'node:assert/strict';
import test from 'node:test';
import { compassPageAction } from '../scripts/compass_navigation.mjs';

// Small rendered-DOM model; no framework internals or simulated network API.
class Element {
  constructor(tag, label = '', attrs = {}, children = []) {
    this.tag = tag; this.label = label; this.attrs = attrs; this.children = children;
    this.className = attrs.class || ''; this.value = attrs.value || ''; this.clicks = 0;
    children.forEach(child => { child.parentElement = this; });
  }
  get innerText() { return [this.label, ...this.children.map(child => child.innerText)].filter(Boolean).join('\n'); }
  getClientRects() { return this.hidden || this.parentElement?.getClientRects().length === 0 ? [] : [{}]; }
  getAttribute(name) { return this.attrs[name] ?? null; }
  click() { this.clicks++; }
  querySelectorAll(selector) {
    const matches = element => selector.split(',').some(part => {
      const match = part.trim().match(/^(\w+)?(?:\[([\w-]+)(\*=|\^=|=)"([^"]*)"\])?$/);
      if (!match || (match[1] && match[1] !== element.tag)) return false;
      if (!match[2]) return true;
      const actual = element.getAttribute(match[2]) || '';
      return match[3] === '*=' ? actual.includes(match[4]) : match[3] === '^=' ? actual.startsWith(match[4]) : actual === match[4];
    });
    return this.children.flatMap(child => [...(matches(child) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
}
const el = (...args) => new Element(...args);
const row = (name, options) => el('div', '', {}, [el('span', name), ...options]);
function withPage(children, action) {
  const previous = globalThis.document;
  globalThis.document = el('body', '', {}, children);
  try { action(); } finally { globalThis.document = previous; }
}

test('category price loading cannot borrow the brand row unlimited option', () => {
  const brandAll = el('button', '不限'), custom = el('button', '自定义');
  withPage([row('品牌类型', [brandAll]), row('价格带', [custom])], () => {
    assert.deepEqual(compassPageAction('price', '0-50'), { pending: true });
    assert.equal(brandAll.clicks, 0);
    assert.equal(custom.clicks, 0);
  });
});

test('category-specific bands use the official custom entry instead of a different price', () => {
  const native = el('button', '0-40'), custom = el('button', '自定义');
  withPage([row('价格带', [el('button', '不限'), native, custom])], () => {
    assert.deepEqual(compassPageAction('price', '0-50'), { price_band: '0-50', custom: true });
    assert.equal(native.clicks, 0);
    assert.equal(custom.clicks, 1);
  });
});

test('equivalent currency and separator formats still use the matching preset', () => {
  const native = el('button', '￥ 0 ～ 50 元'), custom = el('button', '自定义');
  withPage([row('价格带', [el('button', '不限'), native, custom])], () => {
    assert.equal(compassPageAction('price', '0-50').custom, false);
    assert.equal(native.clicks, 1);
    assert.equal(custom.clicks, 0);
  });
});

test('custom bounds are checked after reopening and a changed upper bound fails closed', () => {
  const min = el('input', '', { placeholder: '输入最小值', value: '0' });
  const max = el('input', '', { placeholder: '输入最大值', value: '40' });
  const cancel = el('button', '取消');
  const dialog = el('div', '', { class: 'aurora-modal-container' }, [min, max, cancel]);
  withPage([dialog], () => {
    assert.throws(() => compassPageAction('price-custom-verify', '0-50'), /未正确填写/);
    assert.equal(cancel.clicks, 0);
    max.value = '50';
    assert.deepEqual(compassPageAction('price-custom-verify', '0-50'), { verified: true });
    assert.equal(cancel.clicks, 1);
  });
});

test('custom selection is not accepted while its dialog remains open', () => {
  const dialog = el('div', '', { class: 'aurora-modal-container' }, [el('input', '', { placeholder: '输入最小值' }), el('input', '', { placeholder: '输入最大值' })]);
  withPage([row('价格带', [el('button', '自定义', { 'aria-pressed': 'true' })]), dialog], () => {
    assert.equal(compassPageAction('price-state', { query: '0-50', custom: true }).applied, false);
    dialog.hidden = true;
    assert.equal(compassPageAction('price-state', { query: '0-50', custom: true }).applied, true);
  });
});
