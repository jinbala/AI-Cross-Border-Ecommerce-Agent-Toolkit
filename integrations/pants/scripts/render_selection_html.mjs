#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

import { buildSelectionReport, renderSelectionHtml } from './selection_core.mjs';
export * from './selection_core.mjs';

function parseArgs(argv) {
  const args = { input: null, outputDir: process.cwd(), output: null, config: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!args.input && !value.startsWith('--')) args.input = value;
    else if (value === '--output-dir') args.outputDir = argv[++index];
    else if (value === '--output') args.output = argv[++index];
    else if (value === '--config') args.config = argv[++index];
    else throw new Error(`unknown argument: ${value}`);
  }
  if (!args.input) throw new Error('usage: render_selection_html.mjs input.json [--output-dir DIR | --output FILE]');
  return args;
}

export function runCli(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  const input = JSON.parse(readFileSync(resolve(args.input), 'utf8').replace(/^\uFEFF/, ''));
  const config = args.config ? JSON.parse(readFileSync(resolve(args.config), 'utf8').replace(/^\uFEFF/, '')) : {};
  const report = buildSelectionReport(input, config);
  const output = args.output
    ? resolve(args.output)
    : resolve(args.outputDir, report.meta.source_type === 'product_ranking' ? `商品榜选品-${report.meta.ranking_date}.html` : `选品结果-${report.meta.ranking_date}-近${report.config.publication_days}日.html`);
  mkdirSync(resolve(output, '..'), { recursive: true });
  writeFileSync(output, renderSelectionHtml(report), 'utf8');
  process.stdout.write(`${output}\n`);
  return output;
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  try {
    runCli();
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
