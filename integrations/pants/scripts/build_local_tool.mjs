import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { CSV_HEADERS, PRODUCT_CSV_HEADERS } from './import_selection.mjs';
import { buildSelectionReport } from './selection_core.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let dataPath = resolve(root, 'results/latest-compass-products.json');
let outputDir = resolve(root, 'results');
for (let i = 2; i < process.argv.length; i += 1) {
  const flag = process.argv[i];
  if (flag === '--data' && process.argv[i + 1]) dataPath = resolve(process.argv[++i]);
  else if (flag === '--output-dir' && process.argv[i + 1]) outputDir = resolve(process.argv[++i]);
  else throw new Error(`未知参数或参数缺少值：${flag}`);
}
let savedInput = null, savedError = '';
if (existsSync(dataPath)) {
  try {
    const input = JSON.parse(readFileSync(dataPath, 'utf8').replace(/^\uFEFF/, ''));
    if (input.meta?.source_type !== 'product_ranking' || input.meta?.is_demo !== false || !input.meta.observed_identity || !input.meta.period || !Array.isArray(input.products) || !input.products.length) throw new Error('需要包含店铺身份、统计周期和商品记录的真实商品榜原始数据');
    const report = buildSelectionReport(input);
    if (report.unresolved.length) throw new Error('缓存存在待核数据，请重新核实采集结果');
    savedInput = input;
  } catch (error) {
    savedError = '上次保存的榜单读取失败：' + error.message;
  }
}
const core = readFileSync(resolve(root, 'scripts/selection_core.mjs'), 'utf8').replace(/^export /gm, '');
const compassCore = readFileSync(resolve(root, 'scripts/compass_core.mjs'), 'utf8').replace(/^export /gm, '');
const priceRangesCore = readFileSync(resolve(root, 'scripts/price_ranges.mjs'), 'utf8').replace(/^export /gm, '');
const importer = readFileSync(resolve(root, 'scripts/import_selection.mjs'), 'utf8').replace(/^export /gm, '');
const demo = JSON.parse(readFileSync(resolve(root, 'tests/fixtures/pants-demo.json'), 'utf8'));
const defaults = JSON.parse(readFileSync(resolve(root, 'config/selection.json'), 'utf8'));
const sources = JSON.parse(readFileSync(resolve(root, 'config/data-sources.json'), 'utf8'));
const productDemo = JSON.parse(readFileSync(resolve(root, 'tests/fixtures/product-ranking-demo.json'), 'utf8'));
const app = readFileSync(resolve(root, 'scripts/local_tool_app.js'), 'utf8');
const factoryScreen = readFileSync(resolve(root, 'scripts/factory_screen.mjs'), 'utf8').replace(/^export /gm, '');
const source = `${core}\n${compassCore}\n${priceRangesCore}\n${importer}\nconst demoInput=${JSON.stringify(demo)};\nconst productDemoInput=${JSON.stringify(productDemo)};\nconst defaults=${JSON.stringify(defaults)};\nconst savedInput=${JSON.stringify(savedInput)};\nconst savedError=${JSON.stringify(savedError)};\n${app}`;
const shell = readFileSync(resolve(root, 'scripts/local_tool_shell.html'), 'utf8');
const links = sources.sources.map(item => `<a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.label} · ${item.purpose}</a>`).join('　');
const html = shell.replace('{{SOURCE_LINKS}}', () => links).replace('{{APP_SCRIPT}}', () => (factoryScreen+'\n'+source).replace(/<\/script/gi, '<\\/script'));
mkdirSync(outputDir, { recursive: true });
writeFileSync(resolve(outputDir, '裤装选品工具.html'), html, 'utf8');
writeFileSync(resolve(outputDir, 'pants-tool.html'), html, 'utf8');
if (!existsSync(resolve(root, '裤装数据模板.csv'))) {
  writeFileSync(resolve(root, '裤装数据模板.csv'), '\uFEFF' + CSV_HEADERS.join(',') + '\r\n', 'utf8');
}
if (!existsSync(resolve(root, '裤装商品榜模板.csv'))) {
  writeFileSync(resolve(root, '裤装商品榜模板.csv'), '\uFEFF' + PRODUCT_CSV_HEADERS.join(',') + '\r\n', 'utf8');
}
console.log(`已生成 ${resolve(outputDir, '裤装选品工具.html')}；${savedInput ? '打开即显示已保存的真实榜单。' : savedError || '尚无已保存的真实榜单。'}`);
