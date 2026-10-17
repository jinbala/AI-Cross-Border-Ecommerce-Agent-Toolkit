import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import { normalizeCompassSnapshots } from './compass_core.mjs';
export { normalizeCompassSnapshots } from './compass_core.mjs';

export function runNormalize(argv) {
  const inputs = []; let output = null, identity;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--output') output = argv[++i];
    else if (argv[i] === '--identity') identity = argv[++i];
    else inputs.push(argv[i]);
  }
  if (!output || !inputs.length) throw new Error('用法：node scripts/normalize_compass_snapshot.mjs 快照.json ... --output 原始商品榜.json [--identity 店铺名]');
  const data = normalizeCompassSnapshots(inputs.map(path => JSON.parse(readFileSync(resolve(path), 'utf8').replace(/^\uFEFF/, ''))), identity);
  mkdirSync(dirname(resolve(output)), { recursive: true });
  const contents = JSON.stringify(data, null, 2) + '\n';
  writeFileSync(resolve(output), contents, 'utf8');
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const latest = resolve(root, 'results/latest-compass-products.json');
  mkdirSync(dirname(latest), { recursive: true });
  if (resolve(output) !== latest) writeFileSync(latest, contents, 'utf8');
  const build = spawnSync(process.execPath, [resolve(root, 'scripts/build_local_tool.mjs')], { cwd: root, encoding: 'utf8', windowsHide: true });
  if (build.error || build.status !== 0) throw new Error(`数据已保存，但工具构建失败：${build.error?.message || build.stderr}`);
  console.log(`已保存 ${data.products.length} 条真实商品榜记录并更新选品工具；重新打开页面即可查看，无需导入。覆盖范围为试采页。`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { runNormalize(process.argv.slice(2)); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
