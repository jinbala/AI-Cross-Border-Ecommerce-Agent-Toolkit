---
name: product-selection-specialist
description: Discover and organize men's and women's pants candidates from authorized Douyin Data Compass data, import local CSV or JSON, and generate a filterable HTML selection report. Use for pants selection, ranking discovery and candidate lists, not purchasing or merchant outreach.
metadata:
  compatibility: Local tooling requires Node.js 22+. Live collection requires an authorized Data Compass browser or data adapter; optional storage requires a configured adapter.
---

# 男女裤装选品

Produce a verifiable screening list for a business selling men's and women's pants. Keep source evidence separate from style guesses and commercial recommendations.

## Choose The Available Input

- For local CSV/JSON, read [the input contract](references/adapter-contract.md). Existing files do not require a live browser.
- Build the local visual tool with `node scripts/build_local_tool.mjs`, then deliver `results/裤装选品工具.html`. The Windows launcher is `打开裤装选品.cmd`.
- Live collection needs an authorized browser/data adapter. `scripts/capture_compass_product.mjs` exports a visible-DOM current-page capture function for the connected Playwright MCP; `scripts/normalize_compass_snapshot.mjs` converts saved snapshots to product input. There is no unattended paginator. Report missing capability instead of inventing current products.
- After live product capture, run the normalizer CLI with snapshot paths, `--output` and the verified `--identity`. It automatically saves `results/latest-compass-products.json` and rebuilds the local tool. Opening the tool then loads and renders this saved real data without templates or manual import. Do not ask the user to fill fields already available from the authorized page. Show its actual period and partial scope; refreshing HTML does not fetch new platform data.
- Demo requests use `tests/fixtures/pants-demo.json`. Preserve `meta.is_demo=true`; demo work IDs must not generate live Douyin links.
- Read `config/data-sources.json` for the four user-provided shop/chance entry URLs. Product ranking is the current business's primary source. User-provided URLs establish the intended destination, not login, category or field verification. Category mining/overview and shop rankings are navigation-only; do not invent product records from them.
- Product-ranking files use `meta.source_type=product_ranking` and a `products` array; the demo is `tests/fixtures/product-ranking-demo.json`. They require no works, new-entry flags or publication dates. Price and gender rules still apply, and content repetition/account counts are not available. Graphic files use `graphic_ranking` (also the legacy JSON default) and `relations`. The local tool defaults to product mode and auto-selects the JSON source on import.

## Configuration

Read `config/selection.json` for this business's defaults. Explicit user values override defaults.

- `publication_days`: 1–90 complete calendar dates ending on ranking date; default 3.
- `price_floor` / `price_ceiling`: inclusive numeric bounds, defaults 0 / ¥1000. Missing prices stay as 待验证.
- `price_basis`: CLI defaults to `sku_min`; the product workbench explicitly defaults to `price_band`. Band mode uses inclusive interval overlap against the source price band, falling back to a known SKU minimum when no band can be parsed. Unknown prices stay visible with feedback. Never write the parsed band into `product.price_min`. Graphic UI keeps SKU-minimum filtering.
- `require_new_entry`: default true. Rank increases are not new-entry evidence. If explicitly false, describe recent-publication observation rather than new entries.
- `gender`: 全部、男款、女款、中性款. With a specific requested gender, unknown gender goes to the unresolved ledger.
- `timezone`: Asia/Shanghai. Convert offset timestamps before filtering; unzoned local timestamps use business time.

CLI precedence: built-in defaults, input JSON `config`, explicit `--config` file. The visual tool uses its displayed controls as explicit overrides.

```bash
node scripts/render_selection_html.mjs input.json --config config/selection.json --output-dir results
```

The publication window is not a historical-ranking merge. Multi-day sales trends require actual daily snapshots and are not implemented by changing the window.

## Live Collection Gate

Read [workflow](references/workflow.md) for collection and coverage semantics. Read back the intended Data Compass identity, source, selected ranking, actual period, date/range and category path. Graphic mode verifies `图文直接成交榜 / 近1天` and latest completed ranking date. Product mode verifies `/shop/chance/rank-product` and its visible 商品榜单 state; do not force a one-day period or yesterday onto a different selected period. An open page does not prove identity. Stop the live run if login, identity, CAPTCHA, permissions, ranking state or shared-session safety cannot be verified.

Read [the pants catalog](references/category-catalog.yaml). On 2026-10-13 the authorized visible menu verified 8 male and 6 female pants leaf paths under 服饰内衣 / 服装 / 男装 or 女装. Select exact `scan_nodes`; do not append 全部 or collect the all-clothing aggregate. Menu verification does not establish collection coverage. Only female jeans and male casual pants first pages have been sampled. Business tags are not menu entries. Reverify if the UI changes; do not rescan the whole menu on normal runs. `references/category-catalog.legacy.yaml` retains the former five-category catalog, not the pants default.

Use one shared account serially. Graphic nodes target TOP200 or a proven natural end. For product nodes first verify the page's actual supported range, then record the agreed scan depth and actual completion. Retry a healthy node once; after two failed attempts record incomplete coverage and continue only while the platform gate stays healthy. Do not claim platform-wide completeness.

## Normalize And Screen

Keep original IDs as strings, category paths, ranking dates, `is_new`, publication times and source metrics. Preserve missing fields; never infer unavailable fabric, sizes, gender, commission or profit.

The shared renderer performs:

1. Exact `(product.id, work.id)` deduplication, retaining the first-scanned category path.
2. Per-relation ranking-date validation, business-time publication filtering, configured new-entry and price rules, then explicit gender filtering.
3. Product-ID grouping with every work retained and best rank as representative.
4. Distinct work counts and distinct **known account** counts. Multiple works from one account are not multiple accounts; missing accounts are counted separately.
5. Stable sorting by rank, work count, publication time and ID.

Labels: 单次出现、重复出现、多作品出现（3–4）、高频出现（5+）. Repetition is an observation signal, not permission to copy content or a demand/profit guarantee. Similar-looking products with different IDs stay separate; the tool cannot certify identical goods or factory origin.

Display 最低可购买价 and SKU price scope separately. Do not assume the cheapest SKU is the desired pants variant; missing scope stays 待验证.

The verified product page exposes 用户支付金额, 点击次数, 成交件数 and 点击成交转化率 as display ranges. Preserve their names and units. Display the source 价格带 explicitly; it is not a verified minimum SKU price: keep `price_min=null`. Actual rank is the suffix in the observed DOM row key; top-three rank icons have no text, and rank-cell delta text must not become rank or new-entry evidence. A disabled 查看详情 button does not prove that the title has no link. Check the visible product title anchor first; if clicking the title normally opens a page, capture that observed URL and match it back to the product. Do not inspect private framework state or fabricate routes from IDs. Follow the temporary-tab budget. Render a captured product URL on both the title and the detail button. Snapshots with changed headers, mismatched identities or periods must fail normalization. Record trial coverage as partial.

## Links And Browser Tabs

Capture product links separately. For real work IDs construct `https://www.douyin.com/video/{作品ID}`; 不打开验证 by default. Never substitute product URLs for work URLs or claim validity without checking. Explicit link-verification requests require a supported verification step outside this discovery tool.

Use a **zero-residency** policy for unavoidable detail clicks. Normally keep one temporary product-detail tab; allow at most three temporary product-detail tabs. Capture the ID/link, close immediately and return to the pre-click tab baseline before the next product. On leakage pause collection and use [failure handling](references/failure-handling.md). Never close unrelated user tabs.

## Delivery And Storage

Deliver product-mode `商品榜选品-YYYY-MM-DD.html`, or graphic-mode `选品结果-YYYY-MM-DD-近N日.html`, with effective filters, apparel attributes, source evidence, links, coverage and unresolved records. Product mode must not claim a publication window, content repetition or known creator counts. The local tool also downloads structured report JSON; reports are not raw inputs. Honor explicit text requests without changing filters.

Coverage is complete only with expected nodes supplied and all nodes having both `status=complete` and `reached_top_200_or_end=true`, with no failures. Manual files without evidence have unknown coverage.

Storage/飞书 sync is an explicit separate branch requiring a storage adapter. Preserve candidate policy, raw/candidate separation and idempotency. Report inserted/existing/failed counts, stopping at confirmed destination write. A list request does not authorize writes.

Never export session secrets or bypass platform controls. Stop before samples, merchant contact, cart/showcase or other business actions unless separately requested and supported.
