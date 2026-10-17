// Bundled with the shared importer/renderer and saved data by build_local_tool.mjs.
let loaded = null, currentReport = null, currentView = null, outputHtml = '';
let currentSavedInput = savedInput;
const desktopBridge = globalThis.PANTS_DESKTOP && globalThis.chrome?.webview;
let chosenPriceBands = new Set(), priceUnlimited = Boolean(desktopBridge);
let activeSection = 'workbench', pricePresets = [];
let favorites = new Set(), favoriteKey = '';
const searchIndex = new WeakMap();
let cardPage = 0, factoryResults = new WeakMap();
const cardsPerPage = 80;
let categoryPaths = Object.entries(PANTS).flatMap(([gender, names]) => names.map(name => ['服饰内衣', '服装', gender, name]));
let selectedCategories = new Set(categoryPaths.filter(path => (path[2] === '女装' && path[3] === '牛仔裤') || (path[2] === '男装' && path[3] === '休闲裤')).map(path => JSON.stringify(path)));
const el = id => document.getElementById(id);
const storagePlace = globalThis.PANTS_DESKTOP ? '桌面版（本机）' : '当前浏览器';
el('factory-sales').value = '0'; el('factory-conversion').value = '0';
try {
  const saved = JSON.parse(localStorage.getItem('garment-factory-screen-v1') || 'null');
  if (saved && Number.isFinite(saved.minSales) && saved.minSales >= 0 && Number.isFinite(saved.minConversion) && saved.minConversion >= 0 && saved.minConversion <= 100 && typeof saved.keywords === 'string') {
    el('factory-sales').value = saved.minSales; el('factory-conversion').value = saved.minConversion;
    el('factory-keywords').value = saved.keywords; el('factory-only').checked = saved.only === true;
  }
} catch {}
function factoryPreferences() { return {minSales:Number(el('factory-sales').value), minConversion:Number(el('factory-conversion').value), keywords:el('factory-keywords').value, only:el('factory-only').checked}; }
function renderCategoryChoices() {
  el('category-choices').innerHTML = categoryPaths.map((path, index) => '<button type="button" data-category="'+index+'" aria-pressed="'+selectedCategories.has(JSON.stringify(path))+'">'+escapeHtml(path.slice(2).join(' / '))+'</button>').join('');
  el('custom-category-panel').hidden = el('update-scope').value !== 'custom';
}
function saveCategories() {
  try { localStorage.setItem('garment-category-settings-v1', JSON.stringify({paths:categoryPaths, selected:[...selectedCategories]})); } catch {}
}
try {
  const saved = JSON.parse(localStorage.getItem('garment-category-settings-v1') || 'null');
  if (saved && Array.isArray(saved.paths) && saved.paths.length <= 200 && saved.paths.every(path => Array.isArray(path) && path.length === 4 && path[0] === '服饰内衣' && path[1] === '服装' && ['男装','女装'].includes(path[2]) && path.every(part => typeof part === 'string' && part.trim() && part.length <= 100) && path[3] !== '全部')) {
    categoryPaths = saved.paths;
    if (Array.isArray(saved.selected)) selectedCategories = new Set(saved.selected.filter(key => categoryPaths.some(path => JSON.stringify(path) === key)));
  }
} catch {}
for (const [id, key] of [['days', 'publication_days'], ['floor', 'price_floor'], ['ceiling', 'price_ceiling'], ['gender', 'gender']]) el(id).value = defaults[key];
el('new-only').checked = defaults.require_new_entry;
el('source-type').value = 'product_ranking';
el('price-basis').value = defaults.price_basis || 'price_band';
el('type').value = ''; el('query').value = ''; el('sort').value = 'rank';

function notice(message, error = false) {
  el('status').hidden = false;
  el('status').textContent = message; el('status').className = error ? 'error' : 'status';
}
function syncMode() {
  const productMode = el('source-type').value === 'product_ranking';
  el('days').disabled = productMode; el('new-only').disabled = productMode;
  el('graphic-options').hidden = productMode;
  el('price-basis').disabled = !productMode;
  el('mode-help').textContent = productMode ? '商品榜按实际统计周期选款。可按页面价格带筛选，不要求已核实 SKU 最低价。' : '图文榜按作品发布时间和新上榜标记筛选，价格使用已核实最低价。';
  for (const [id, gender] of [['all', '全部'], ['women', '女款'], ['men', '男款']]) el(id).setAttribute('aria-pressed', String(el('gender').value === gender));
}
function selectedPriceRanges() {
  const ranges = [...chosenPriceBands].map(id => COMPASS_PRICE_BANDS.find(band => band.id === id)).filter(Boolean).map(({ min, max }) => ({ min, max }));
  const custom = parseCustomPriceRanges(el('custom-ranges').value);
  if (ranges.length || custom.length) return normalizePriceRanges([...ranges, ...custom]);
  return priceUnlimited ? [] : null;
}
function syncPriceButtons() {
  el('price-all').setAttribute('aria-pressed', String(priceUnlimited && !chosenPriceBands.size && !el('custom-ranges').value.trim()));
  for (const band of COMPASS_PRICE_BANDS) el('band-' + band.id).setAttribute('aria-pressed', String(chosenPriceBands.has(band.id)));
  try { const ranges = selectedPriceRanges(); el('price-summary').textContent = ranges === null ? '按单段区间' : priceRangesLabel(ranges); }
  catch { el('price-summary').textContent = '请检查价格区间'; }
}
function updateCollectionSummary() {
  if (!desktopBridge) return;
  try {
    const options = desktopUpdateOptions();
    const count = options.preset === 'custom' ? options.category_paths.length : {common:2, women:6, men:8, all:14}[options.preset];
    el('update-summary').textContent = `${options.period} · ${count} 类 × ${options.price_queries.length} 个价位 · 最多 ${count * options.price_queries.length * options.limit} 条`;
    el('update-plan').textContent = '切换价位只筛选已保存数据；点击“立即更新”按当前条件取新榜单。' + (options.collect_links ? '完整模式会逐件补商品链接。' : '快速读榜跳过逐件补链接，仍保留页面已有链接；缺少链接时可复制商品名查找。');
  } catch (error) { el('update-plan').textContent = error.message; }
}
function priceChanged() {
  syncPriceButtons(); if (loaded) generate();
  try {
    selectedPriceRanges();
    try { localStorage.setItem('pants-price-filter-v1', JSON.stringify({ bands: [...chosenPriceBands], custom: el('custom-ranges').value, unlimited: priceUnlimited, floor: Number(el('floor').value), ceiling: Number(el('ceiling').value) })); } catch {}
    updateCollectionSummary();
  } catch {}
}
function renderSection() {
  const settings = activeSection === 'settings';
  if (desktopBridge) el('desktop-update').hidden = activeSection === 'favorites';
  if (settings) el('collection-options').open = true;
  el('filter-panel').hidden = settings;
  el('list-heading').hidden = settings;
  if (settings) { el('product-board').hidden = true; el('preview').hidden = true; }
  el('list-title').textContent = activeSection === 'favorites' ? '我的收藏' : '选品清单';
}
function clearResult() {
  outputHtml = ''; currentReport = null; currentView = null;
  cardPage = 0; el('card-pages').hidden = true;
  el('preview').removeAttribute('srcdoc'); el('cards').innerHTML = '';
  for (const id of ['download', 'json-download', 'csv-download']) el(id).disabled = true;
  el('view-count').textContent = '暂无结果';
  el('price-feedback').textContent = '';
}
function loadFavorites(input) {
  const key = 'pants-favorites-v1:' + (input.meta?.is_demo ? 'demo:' : 'real:') + (input.meta?.observed_identity || 'manual');
  if (key === favoriteKey) return;
  favoriteKey = key; favorites = new Set();
  try {
    const ids = JSON.parse(localStorage.getItem(key) || '[]');
    if (!Array.isArray(ids) || ids.some(id => typeof id !== 'string')) throw new Error('invalid favorites');
    favorites = new Set(ids);
    el('favorite-note').textContent = '收藏保存在' + storagePlace + '，下次打开可以继续看。';
  } catch {
    el('favorite-note').textContent = '当前浏览器无法读取已存收藏；本次仍可挑款。';
  }
}
function metric(label, value) {
  return '<span>' + escapeHtml(label) + '<b>' + escapeHtml(value ?? '待验证') + '</b></span>';
}
function renderCard(group) {
  const product = group.product, observation = group.primary_observation;
  const metrics = observation?.metrics || {};
  const favorite = favorites.has(product.id);
  const link = safeHttpUrl(product.link);
  const price = productPricePresentation(product);
  const assessment = factoryResults.get(group) || factoryScreen(group, factoryPreferences());
  return '<article class="product-card"><div class="card-top"><span class="rank">' + escapeHtml(observation?.source_filters?.price_band_label || '') + ' 榜内第 ' + escapeHtml(observation?.rank ?? '—') + ' 名</span><span class="tag">' + escapeHtml(product.apparel?.gender || '款别待核') + ' · ' + escapeHtml(product.apparel?.type || '品类待核') + '</span><button type="button" class="favorite ' + (favorite ? 'selected' : '') + '" data-favorite="' + escapeHtml(product.id) + '" aria-pressed="' + favorite + '" aria-label="' + (favorite ? '取消收藏：' : '收藏：') + escapeHtml(product.name) + '">' + (favorite ? '★ 已收藏' : '☆ 收藏') + '</button></div>'
    + '<h2>' + (link ? '<a class="product-title" href="' + escapeHtml(link) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(product.name) + '</a>' : escapeHtml(product.name)) + '</h2><p class="shop">' + escapeHtml(product.shop || '店铺待核') + '</p>'
    + '<div class="price"><span class="price-label">' + escapeHtml(price.label) + '</span>' + escapeHtml(price.value) + '<small>' + (price.isBand ? '页面展示值 · SKU 最低价待核实' : group.price_status === '待验证' ? 'SKU 最低价待核实' : '已读取的价格') + '</small></div>'
    + '<div class="card-metrics">' + metric('用户支付金额', metrics.payment_amount ?? metrics.transaction_amount) + metric('成交件数', metrics.sales_count) + metric('点击次数', metrics.clicks) + metric('点击成交转化率', metrics.click_conversion_rate) + '</div>'
    + (assessment.active ? '<div class="factory-assessment '+(assessment.qualifies?'match':assessment.missing?'pending':'observe')+'"><b>'+escapeHtml(assessment.label)+'</b><p>'+escapeHtml(assessment.reasons.join('；'))+'</p><small>下一步：核实面料、工艺、起订量，再填写本厂成本算利润。</small></div>' : '')
    + '<div class="product-actions">' + (link ? '<a class="button product-link" href="' + escapeHtml(link) + '" target="_blank" rel="noopener noreferrer">打开商品</a>' : '<span class="link-missing">商品链接暂缺</span>')
    + '<button type="button" data-copy-product="' + escapeHtml(product.id) + '" data-copy-field="name">复制商品名</button><button type="button" data-copy-product="' + escapeHtml(product.id) + '" data-copy-field="id">复制商品 ID</button></div>'
    + (link ? '' : '<p class="hint">可复制商品名到罗盘查找；如需批量补链接，关闭“快速读榜”后重新更新。</p>')
    + '<details><summary>类目与商品信息</summary><p>' + escapeHtml(group.category_path.join(' / ')) + '</p><p>查询价位：' + escapeHtml(observation?.source_filters?.price_band_label || '不限价格') + ' · 排名为该查询条件下的榜内名次</p><p>商品 ID：' + escapeHtml(product.id) + '</p></details></article>';
}
function applyView(resetPage = true) {
  if (!currentReport) return;
  const query = el('query').value.trim().toLowerCase(), type = el('type').value;
  const onlyFavorites = el('only-favorites').checked;
  const preferences = factoryPreferences();
  factoryResults = new WeakMap();
  try { factoryScreen({product:{}}, preferences); } catch (error) { notice(error.message,true); return; }
  let groups = currentReport.groups.filter(group => {
    if (!searchIndex.has(group)) searchIndex.set(group,[group.product.name, group.product.shop, group.product.id, ...Object.values(group.product.apparel || {}), ...group.works.map(work => [work.work?.title, work.work?.author, work.work?.account].join(' '))].join(' ').toLowerCase());
    const matches=(!query || searchIndex.get(group).includes(query)) && (!type || group.product.apparel?.type === type) && (!onlyFavorites || favorites.has(group.product.id));
    if(!matches || !preferences.only)return matches;
    const assessment=factoryScreen(group,preferences);factoryResults.set(group,assessment);return assessment.qualifies;
  });
  if (el('sort').value === 'favorite') groups = groups.slice().sort((a, b) => Number(favorites.has(b.product.id)) - Number(favorites.has(a.product.id)));
  const labels = [el('gender').value, type, query && '搜索“' + el('query').value.trim() + '”', onlyFavorites && '只看收藏'].filter(Boolean);
  if (preferences.only) labels.push(`工厂初筛：成交下限≥${preferences.minSales}，转化下限≥${preferences.minConversion}%，关键词：${preferences.keywords || '不限'}`);
  currentView = { ...currentReport, groups, summary: { ...currentReport.summary, unique_products: groups.length, qualified_relations: groups.reduce((count, group) => count + (group.is_product_ranking ? group.observations.length : group.works.length), 0) }, meta: { ...currentReport.meta, view_filters: labels, collection_scope: [currentReport.meta.collection_scope, '导出视图：' + labels.join(' / ')].filter(Boolean).join('；') } };
  const productMode = currentReport.meta.source_type === 'product_ranking';
  // Desktop product cards already present the report. Build its export only on demand.
  const lazyExport = desktopBridge && productMode;
  outputHtml = lazyExport ? '' : renderSelectionHtml(currentView);
  if(lazyExport)el('preview').removeAttribute('srcdoc');else el('preview').srcdoc = outputHtml;
  el('preview').hidden = productMode; el('product-board').hidden = !productMode;
  const paged = Boolean(desktopBridge && productMode);
  if(resetPage)cardPage=0;
  cardPage=Math.min(cardPage,Math.max(0,Math.ceil(groups.length/cardsPerPage)-1));
  const visible=paged?groups.slice(cardPage*cardsPerPage,(cardPage+1)*cardsPerPage):groups;
  el('cards').innerHTML = productMode ? visible.map(renderCard).join('') : '';
  el('card-pages').hidden = !paged || groups.length <= cardsPerPage;
  el('card-page-label').textContent='第 '+(cardPage+1)+' / '+Math.max(1,Math.ceil(groups.length/cardsPerPage))+' 页 · 每页 '+cardsPerPage+' 款';
  el('card-prev').disabled=cardPage===0;el('card-next').disabled=(cardPage+1)*cardsPerPage>=groups.length;
  el('empty').hidden = groups.length !== 0;
  el('view-count').textContent = '筛选结果 ' + groups.length + ' 件 / 筛选前 ' + currentReport.groups.length + ' 件' + (paged && groups.length ? ' · 本页第 '+(cardPage*cardsPerPage+1)+'–'+Math.min((cardPage+1)*cardsPerPage,groups.length)+' 件' : '');
  el('favorite-count').textContent = '当前范围已收藏 ' + currentReport.groups.filter(group => favorites.has(group.product.id)).length + ' 件';
  const unknownPrices = groups.filter(group => group.price_filter_basis === 'unknown').length;
  el('price-feedback').className = 'hint';
  el('price-feedback').textContent = '符合当前条件 ' + groups.length + ' 件。' + currentReport.meta.price_rule + '。' + (unknownPrices ? '当前有 ' + unknownPrices + ' 件价格无法判定，已保留；若只有价格带，请选择“页面价格带”。' : '当前显示的商品均有可用于价格筛选的依据。');
  for (const id of ['download', 'json-download', 'csv-download']) el(id).disabled = groups.length === 0;
  renderSection();
}
function generate() {
  clearResult(); syncMode();
  try {
    if (!loaded) throw new Error('请先导入 CSV/JSON，或点击“体验演示”');
    const productMode = el('source-type').value === 'product_ranking';
    const priceRanges = productMode ? selectedPriceRanges() : null;
    if ((productMode ? priceRanges === null ? ['floor', 'ceiling'] : [] : ['days', 'floor', 'ceiling']).some(id => !el(id).value.trim())) throw new Error('请填写价格上下限和需要的天数');
    const input = loaded.kind === 'csv' ? importCsv(loaded.text, el('date').value, el('source-type').value) : structuredClone(loaded.input);
    if (loaded.kind === 'json' && (input.meta?.source_type || 'graphic_ranking') !== el('source-type').value) throw new Error('当前模式与 JSON 来源不一致，请切回对应模式或导入匹配的数据');
    if (loaded.kind === 'json' && el('date').value && el('date').value !== input.meta?.ranking_date) throw new Error('榜单日期与 JSON 不一致；请勿修改日期伪装成新数据');
    loadFavorites(input);
    const report = buildSelectionReport(input, { publication_days: productMode ? 3 : Number(el('days').value), price_floor: priceRanges === null ? Number(el('floor').value) : 0, price_ceiling: priceRanges === null ? Number(el('ceiling').value) : 1000, price_ranges: priceRanges, price_basis: productMode ? el('price-basis').value : 'sku_min', gender: el('gender').value, require_new_entry: el('new-only').checked, timezone: 'Asia/Shanghai' });
    currentReport = report;
    const sourceRows = productMode ? input.products : input.relations;
    const previousType = el('type').value;
    const types = [...new Set([...sourceRows.map(row => row.product?.apparel?.type), previousType].filter(Boolean))].sort();
    el('type').innerHTML = '<option value="">全部裤型</option>' + types.map(type => '<option value="' + escapeHtml(type) + '">' + escapeHtml(type) + '</option>').join('');
    el('type').value = types.includes(previousType) ? previousType : '';
    el('date').readOnly = loaded.kind === 'json';
    notice((report.meta.is_demo ? '演示数据 · ' : '') + '入选 ' + report.summary.unique_products + ' 个商品 / ' + report.summary.qualified_relations + ' 条记录；价格排除 ' + report.summary.price_excluded + '，款别排除 ' + report.summary.gender_excluded + '，待核 ' + report.summary.unresolved + '。' + (report.coverage_state.complete ? '计划范围已完成。' : '覆盖未证实，不代表全量。'));
    if (desktopBridge) el('status').hidden = true;
    applyView();
  } catch (error) { notice(error.message, true); el('price-feedback').className = 'error'; el('price-feedback').textContent = '未能应用筛选：' + error.message; }
}
function download(contents, name, type) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function resetFilters() {
  chosenPriceBands.clear(); el('custom-ranges').value = ''; priceUnlimited = Boolean(desktopBridge); syncPriceButtons();
  for (const [id, key] of [['days', 'publication_days'], ['floor', 'price_floor'], ['ceiling', 'price_ceiling']]) el(id).value = defaults[key];
  el('gender').value = '全部'; el('query').value = ''; el('type').value = ''; el('sort').value = 'rank';
  el('new-only').checked = defaults.require_new_entry; el('only-favorites').checked = activeSection === 'favorites';
  el('price-basis').value = defaults.price_basis || 'price_band';
  el('factory-sales').value = '0'; el('factory-conversion').value = '0'; el('factory-keywords').value = ''; el('factory-only').checked = false;
  try { localStorage.removeItem('garment-factory-screen-v1'); } catch {}
  if (loaded) generate();
}
function useSavedRanking() {
  if (!currentSavedInput) return;
  loaded = { kind: 'json', input: structuredClone(currentSavedInput) };
  el('source-type').value = 'product_ranking'; el('date').value = currentSavedInput.meta.ranking_date; el('file').value = '';
  el('source').textContent = '已保存的真实榜单 · ' + currentSavedInput.meta.observed_identity + ' · ' + currentSavedInput.meta.period + ' · ' + currentSavedInput.products.length + ' 条';
  const savedTime = new Date(currentSavedInput.meta.generated_at);
  const timeText = Number.isNaN(savedTime.valueOf()) ? '未记录' : savedTime.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  el('saved-scope').textContent = (currentSavedInput.meta.collection_scope || '采集范围以报告覆盖情况为准。') + '；保存时间：' + timeText + (desktopBridge ? '。更新进度见上方状态；离线或更新失败时继续显示已保存数据。' : '。这是已保存的数据，打开页面不会自动刷新罗盘。');
  generate();
}
el('saved').disabled = !currentSavedInput; el('saved').addEventListener('click', () => { useSavedRanking(); resetFilters(); });
for (const [id, gender] of [['all', '全部'], ['women', '女款'], ['men', '男款']]) el(id).addEventListener('click', () => { el('gender').value = gender; generate(); });
for (const id of ['date', 'days', 'floor', 'ceiling', 'price-basis', 'gender', 'new-only', 'source-type']) {
  for (const event of ['input', 'change']) el(id).addEventListener(event, () => {
    if (['floor', 'ceiling'].includes(id)) { chosenPriceBands.clear(); el('custom-ranges').value = ''; priceUnlimited = false; syncPriceButtons(); }
    syncMode(); if (loaded) generate();
    if (['floor', 'ceiling'].includes(id)) { try { desktopUpdateOptions(); priceChanged(); } catch {} }
  });
}
for (const id of ['query', 'type', 'sort', 'only-favorites']) {
  for (const event of ['input', 'change']) el(id).addEventListener(event, applyView);
}
for (const id of ['factory-sales', 'factory-conversion', 'factory-keywords', 'factory-only']) {
  for (const event of ['input','change']) el(id).addEventListener(event, () => {
    applyView();
    const prefs = factoryPreferences();
    if (prefs.minSales >= 0 && prefs.minConversion >= 0 && prefs.minConversion <= 100) try {localStorage.setItem('garment-factory-screen-v1',JSON.stringify(prefs));} catch {}
  });
}
for (const [id,sales,conversion,only] of [['factory-starter',100,3,true],['factory-clear',0,0,false]]) el(id).addEventListener('click', () => {
  el('factory-sales').value = sales; el('factory-conversion').value = conversion; el('factory-only').checked = only;
  if (!only) el('factory-keywords').value = '';
  el('factory-options').open = only;
  try {localStorage.setItem('garment-factory-screen-v1',JSON.stringify(factoryPreferences()));} catch {}
  applyView();
  if (only) el('list-heading').scrollIntoView?.({block:'start',behavior:'smooth'});
});
for (const id of ['reset', 'empty-reset']) el(id).addEventListener('click', () => { resetFilters(); if (desktopBridge) priceChanged(); });
el('generate').addEventListener('click', () => { chosenPriceBands.clear(); el('custom-ranges').value = ''; priceUnlimited = false; syncPriceButtons(); generate(); });
for (const band of COMPASS_PRICE_BANDS) el('band-' + band.id).addEventListener('click', () => {
  if (chosenPriceBands.has(band.id)) chosenPriceBands.delete(band.id); else chosenPriceBands.add(band.id);
  priceUnlimited = !chosenPriceBands.size && !el('custom-ranges').value.trim(); priceChanged();
});
el('price-all').addEventListener('click', () => { chosenPriceBands.clear(); el('custom-ranges').value = ''; priceUnlimited = true; priceChanged(); });
for (const event of ['input', 'change']) el('custom-ranges').addEventListener(event, () => { priceUnlimited = !chosenPriceBands.size && !el('custom-ranges').value.trim(); priceChanged(); });
try { pricePresets = JSON.parse(localStorage.getItem('pants-price-presets-v1') || '[]'); if (!Array.isArray(pricePresets)) pricePresets = []; pricePresets = pricePresets.slice(0, 10).filter(p => { try { normalizePriceRanges(p.ranges); return typeof p.label === 'string'; } catch { return false; } }); } catch { pricePresets = []; }
function renderPricePresets() { el('price-preset').innerHTML = '<option value="">选择已保存的价位组合</option>' + pricePresets.map((p, i) => '<option value="' + i + '">' + escapeHtml(p.label) + '</option>').join(''); }
renderPricePresets();
el('save-price-preset').addEventListener('click', () => {
  try {
    const ranges = selectedPriceRanges() || [{ min: Number(el('floor').value), max: Number(el('ceiling').value) }];
    const label = priceRangesLabel(ranges);
    pricePresets = [{ label, ranges }, ...pricePresets.filter(p => p.label !== label)].slice(0, 10);
    localStorage.setItem('pants-price-presets-v1', JSON.stringify(pricePresets)); renderPricePresets(); notice('已保存常用价位：' + label);
  } catch (error) { notice('未能保存：' + error.message, true); }
});
el('price-preset').addEventListener('change', () => {
  if (el('price-preset').value === '') return;
  const preset = pricePresets[Number(el('price-preset').value)]; if (!preset) return;
  chosenPriceBands.clear(); el('custom-ranges').value = preset.ranges.map(r => r.max === null ? r.min + '以上' : r.min + '-' + r.max).join('；'); priceUnlimited = !preset.ranges.length; priceChanged();
});
el('cards').addEventListener('click', async event => {
  if (!currentReport) return;
  const button = event.target.closest('[data-favorite]');
  if (button?.dataset.favorite) {
    const id = button.dataset.favorite;
    if (!currentReport.groups.some(group => group.product.id === id)) return;
    if (favorites.has(id)) favorites.delete(id); else favorites.add(id);
    try { localStorage.setItem(favoriteKey, JSON.stringify([...favorites])); el('favorite-note').textContent = '收藏已保存到' + storagePlace + '。'; }
    catch { el('favorite-note').textContent = '收藏仅在本次页面有效；浏览器未允许保存，关闭前可下载清单。'; }
    applyView(false); return;
  }
  const copy = event.target.closest('[data-copy-product]'); if (!copy) return;
  const group = currentReport.groups.find(item => item.product.id === copy.dataset.copyProduct);
  if (!group || !['name', 'id'].includes(copy.dataset.copyField)) return;
  const text = String(group.product[copy.dataset.copyField] || '');
  const label = copy.dataset.copyField === 'id' ? '商品 ID' : '商品名';
  try {
    await navigator.clipboard.writeText(text);
    el('copy-fallback').hidden = true; notice(label + '已复制。查找商品时请核对店铺和款式。');
  } catch {
    el('copy-fallback').hidden = false; el('copy-value').value = text;
    el('copy-value').focus?.(); el('copy-value').select?.();
    notice('浏览器未允许自动复制，请复制下方选中的' + label + '。');
  }
});
el('file').addEventListener('change', async event => {
  clearResult(); loaded = null; el('source').textContent = '尚未导入数据'; el('saved-scope').textContent = '';
  const file = event.target.files[0]; if (!file) return;
  try {
    const text = (await file.text()).replace(/^\uFEFF/, '');
    if (file.name.toLowerCase().endsWith('.json')) {
      const input = JSON.parse(text); loaded = { kind: 'json', input }; el('date').value = input.meta?.ranking_date || ''; el('source-type').value = input.meta?.source_type || 'graphic_ranking';
    } else {
      loaded = { kind: 'csv', text }; const [headers, ...rows] = parseCsv(text); const col = headers?.findIndex(item => item.trim() === '榜单日期');
      const dates = [...new Set(rows.map(row => row[col]?.trim()).filter(Boolean))]; el('date').value = dates.length === 1 ? dates[0] : '';
    }
    el('source').textContent = '已导入：' + file.name; resetFilters();
  } catch (error) { loaded = null; notice('读取失败：' + error.message, true); }
});
el('demo').addEventListener('click', () => {
  const selected = el('source-type').value === 'product_ranking' ? productDemoInput : demoInput;
  loaded = { kind: 'json', input: structuredClone(selected) }; el('date').value = selected.meta.ranking_date; el('file').value = '';
  el('source').textContent = '演示数据（虚构，不是实时榜单）'; el('saved-scope').textContent = ''; resetFilters();
});
el('card-prev').addEventListener('click',()=>{if(cardPage>0){cardPage--;applyView(false);}});
el('card-next').addEventListener('click',()=>{if(currentView&&(cardPage+1)*cardsPerPage<currentView.groups.length){cardPage++;applyView(false);}});
el('download').addEventListener('click', () => { if (currentView?.groups.length) {if(!outputHtml)outputHtml=renderSelectionHtml(currentView);download(outputHtml, (currentView.meta.is_demo ? '演示-' : '') + '裤装清单-' + currentView.meta.ranking_date + '.html', 'text/html;charset=utf-8');} });
el('json-download').addEventListener('click', () => { if (currentView?.groups.length) download(JSON.stringify(currentView, null, 2), '裤装报告-' + currentView.meta.ranking_date + '.json', 'application/json;charset=utf-8'); });
el('csv-download').addEventListener('click', () => {
  if (!currentView?.groups.length) return;
  const cell = value => { let text = String(value ?? ''); if (/^[\s]*[=+\-@]/.test(text)) text = "'" + text; return '"' + text.replaceAll('"', '""') + '"'; };
  const rows = [['榜单日期', '商品ID', '商品名称', '款别', '裤型', '店铺', '榜内排名', '页面价格带', '已核实最低价', '用户支付金额', '成交件数', '点击次数', '点击成交转化率', '已收藏', '来源类目', '商品链接', '查询价位', '当前价格筛选']];
  for (const group of currentView.groups) {
    const p = group.product, observation = group.primary_observation || group.primary_work, m = observation?.metrics || {};
    rows.push([currentView.meta.ranking_date, p.id, p.name, p.apparel?.gender, p.apparel?.type, p.shop, observation?.rank, p.price_band_display || p.price_display, p.price_min, m.payment_amount ?? m.transaction_amount, m.sales_count, m.clicks, m.click_conversion_rate, favorites.has(p.id) ? '是' : '否', group.category_path.join(' / '), safeHttpUrl(p.link), observation?.source_filters?.price_band_label || '不限价格', currentView.meta.price_rule]);
  }
  download('\uFEFF' + rows.map(row => row.map(cell).join(',')).join('\r\n') + '\r\n', '裤装清单-' + currentView.meta.ranking_date + '.csv', 'text/csv;charset=utf-8');
});
el('template').addEventListener('click', () => {
  const productMode = el('source-type').value === 'product_ranking';
  download('\uFEFF' + (productMode ? PRODUCT_CSV_HEADERS : CSV_HEADERS).join(',') + '\r\n', productMode ? '裤装商品榜模板.csv' : '裤装图文榜模板.csv', 'text/csv;charset=utf-8');
});
el('update-copy').addEventListener('click', async () => {
  if (desktopBridge) { startDesktopUpdate(); return; }
  el('update-instruction').hidden = false;
  try { await navigator.clipboard.writeText(el('update-text').textContent); el('copy-status').textContent = '已复制，粘贴到 VS Code 的 Codex 中发送即可。'; }
  catch { el('copy-status').textContent = '请选中下方文字复制，粘贴到 VS Code 的 Codex 中发送。'; }
});
function desktopUpdateOptions() {
  const selected = selectedPriceRanges();
  const ranges = selected === null ? normalizePriceRanges([{ min: Number(el('floor').value), max: Number(el('ceiling').value) }]) : selected;
  const custom = parseCustomPriceRanges(el('custom-ranges').value);
  const queries = chosenPriceBands.size ? [...new Set([...chosenPriceBands, ...(custom.length ? compassQueriesForRanges(custom) : [])])] : compassQueriesForRanges(ranges);
  const category_paths = categoryPaths.filter(path => selectedCategories.has(JSON.stringify(path)));
  if (el('update-scope').value === 'custom' && (!category_paths.length || category_paths.length > 64)) throw new Error('请勾选 1—64 个需要采集的类目');
  return { preset: el('update-scope').value, period: el('update-period').value, limit: Number(el('update-limit').value), price_queries: queries, auto_update: el('auto-update').checked, collect_links: !el('fast-ranking').checked, category_paths };
}
function startDesktopUpdate() {
  if (!desktopBridge || el('update-start').disabled) return;
  try {
    const options = desktopUpdateOptions();
    try { localStorage.setItem('pants-update-settings-v1', JSON.stringify(options)); } catch {}
    desktopBridge.postMessage({ action: 'update-rankings', ...options });
  } catch (error) { el('update-progress').textContent = '未开始更新：' + error.message; }
}
if (desktopBridge) {
  el('desktop-update').hidden = false; el('desktop-progress').hidden = false; el('auto-update').checked = true;
  el('update-scope').value = 'common'; el('update-period').value = '近7天'; el('update-limit').value = '10';
  try {
    const saved = JSON.parse(localStorage.getItem('pants-update-settings-v1') || 'null');
    if (saved && ['common', 'women', 'men', 'all', 'custom'].includes(saved.preset) && ['近1天', '近7天', '近30天'].includes(saved.period) && [10, 20, 50, 200].includes(saved.limit)) {
      el('update-scope').value = saved.preset; el('update-period').value = saved.period; el('update-limit').value = saved.limit;
      el('auto-update').checked = saved.auto_update !== false;
      el('fast-ranking').checked = saved.collect_links === false;
    }
  } catch {}
  el('update-copy').textContent = '立即更新';
  el('desktop-login').addEventListener('click', () => desktopBridge.postMessage({ action: 'open-compass' }));
  el('update-start').addEventListener('click', startDesktopUpdate);
  el('update-stop').addEventListener('click', () => desktopBridge.postMessage({ action: 'stop-update' }));
  for (const id of ['update-scope', 'update-period', 'update-limit', 'auto-update', 'fast-ranking']) el(id).addEventListener('change', () => { renderCategoryChoices(); updateCollectionSummary(); try { localStorage.setItem('pants-update-settings-v1', JSON.stringify(desktopUpdateOptions())); } catch {} });
  el('category-choices').addEventListener('click', event => {
    const button = event.target.closest('[data-category]'); if (!button || el('update-copy').disabled) return;
    const path = categoryPaths[Number(button.dataset.category)]; if (!path) return;
    const key = JSON.stringify(path); if (selectedCategories.has(key)) selectedCategories.delete(key); else selectedCategories.add(key);
    saveCategories(); renderCategoryChoices(); updateCollectionSummary();
  });
  el('discover-categories').addEventListener('click', () => desktopBridge.postMessage({action:'discover-categories'}));
  el('collection-help').textContent = '采集设置可直接在选品页调整。切换价位先筛选本地数据，点击“立即更新”再取新榜单。结果仅限已读取范围；价格带不代表已核实 SKU 最低价。';
  el('saved').hidden = true;
  el('favorite-toolbar').hidden = true;
  globalThis.pantsDesktop = {
    getUpdateOptions: desktopUpdateOptions,
    navigate: section => {
      activeSection = ['workbench', 'favorites', 'settings'].includes(section) ? section : 'workbench';
      el('only-favorites').checked = activeSection === 'favorites';
      if (currentReport) applyView(); renderSection(); return { section: activeSection };
    },
    setUpdateState: state => {
      el('desktop-progress').setAttribute('data-state', state.error ? 'error' : state.busy ? 'busy' : 'idle');
      for (const id of ['update-start', 'update-copy', 'update-scope', 'update-period', 'update-limit', 'fast-ranking', 'discover-categories']) el(id).disabled = state.busy;
      el('update-stop').hidden = !state.busy;
      el('desktop-progress').className = state.busy || state.error ? 'card' : 'idle-progress';
      el('update-progress').className = state.error ? 'error' : 'hint';
      el('update-progress').textContent = state.message;
      return { busy: state.busy };
    },
    setCategories: paths => {
      if (!Array.isArray(paths) || !paths.length || paths.length > 200 || paths.some(path => !Array.isArray(path) || path.length !== 4 || path[0] !== '服饰内衣' || path[1] !== '服装' || !['男装','女装'].includes(path[2]) || path.some(part => typeof part !== 'string' || !part.trim() || part.length > 100) || path[3] === '全部')) throw new Error('类目菜单格式变化，未替换原类目');
      categoryPaths = paths;
      selectedCategories = new Set([...selectedCategories].filter(key => paths.some(path => JSON.stringify(path) === key)));
      saveCategories(); renderCategoryChoices(); updateCollectionSummary();
      el('category-feedback').textContent = '已从当前账号读取 '+paths.length+' 个服装类目。勾选需要的类目即可；读取菜单不会覆盖已保存榜单。';
      return {count:paths.length};
    },
    prepareUpdate: snapshots => ({ snapshots, data: normalizeCompassSnapshots(snapshots, undefined, {allowApparel:true}), replaced_context: false }),
    prepareSnapshot: (previous, snapshot) => mergeCompassSnapshot(previous, snapshot, {allowApparel:true}),
    loadSnapshots: (snapshots, savedAt) => {
      const data = normalizeCompassSnapshots(snapshots, undefined, {allowApparel:true});
      if (savedAt && !Number.isNaN(new Date(savedAt).valueOf())) data.meta.generated_at = savedAt;
      currentSavedInput = data; el('saved').disabled = false;
      useSavedRanking(); syncPriceButtons();
      return { count: data.products.length, identity: data.meta.observed_identity, period: data.meta.period };
    },
  };
}
if (desktopBridge) {
  try {
    const saved = JSON.parse(localStorage.getItem('pants-price-filter-v1') || 'null');
    if (saved && Array.isArray(saved.bands) && saved.bands.every(id => COMPASS_PRICE_BANDS.some(b => b.id === id)) && typeof saved.custom === 'string' && typeof saved.unlimited === 'boolean') {
      parseCustomPriceRanges(saved.custom); chosenPriceBands = new Set(saved.bands); el('custom-ranges').value = saved.custom; priceUnlimited = saved.unlimited;
      if (Number.isFinite(saved.floor) && Number.isFinite(saved.ceiling) && saved.floor >= 0 && saved.ceiling >= saved.floor) { el('floor').value = saved.floor; el('ceiling').value = saved.ceiling; }
    }
  } catch {}
}
syncPriceButtons();
renderCategoryChoices();
updateCollectionSummary();
syncMode();
if (savedInput) useSavedRanking();
else notice(savedError || (desktopBridge ? '首次在左侧“罗盘账号”完成登录，再点“立即更新”。已保存的榜单可离线查看。' : '还没有保存的真实榜单。点击“复制更新指令”，让 Codex 采集一次；完成后重新打开本工具，无需填写模板。'), Boolean(savedError));
