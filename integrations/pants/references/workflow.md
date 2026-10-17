# Pants Discovery Workflow

## Local Files

Import UTF-8 CSV using `裤装数据模板.csv`, or raw JSON matching `adapter-contract.md`. No browser is required. Keep source dates and evidence; do not change historic dates to today. Unknown fields stay missing.

The visual tool reads files locally, allows changing filters, previews results and downloads HTML/report JSON. Its filtering is shared with the CLI in `scripts/selection_core.mjs`.

## Authorized Live Collection

For the current business, prefer the user-provided `/shop/chance/rank-product` 商品榜单. Read its visible source, actual period/date range and category before collecting. Product mode does not require graphic works or new-entry signals and does not assume TOP200 or a one-day period. Category mining/overview and shop ranking are configured navigation links; their table mappings are not implemented. The graphic procedure below applies only to graphic mode.

1. Verify intended identity, Data Compass source, login/challenge state, graphic direct-transaction ranking, one-day period and latest completed ranking date.
2. Verify platform paths against the configured source. Product-menu pants paths were observed on 2026-10-13; this is not verification of graphic-mode menus. Business tags cannot substitute for menu evidence.
3. For product mode use the catalog's exact `scan_nodes`, without appending 全部 or scanning all clothing. For other sources verify their own paths first. Traverse serially to the agreed depth or a proven natural end.
4. Save raw snapshots, normalized products/relations and coverage after each node in the adapter runtime. The repository provides a product current-page DOM reader and converter, but no checkpointing scraper or automatic paginator.
5. Retry a healthy failed node once. Platform gates stop the whole run; node failures may continue with incomplete coverage.
6. Feed raw snapshot and effective configuration to the renderer.

Ranking date 2026-10-12 with `publication_days=3` accepts publications from 2026-10-10 through 2026-10-12 inclusive. Only one ranking snapshot is processed. Disabling `require_new_entry` does not create history or trends.

## Evidence And Coverage

Supply `expected_nodes` as exact path arrays. Completion requires coverage `status=complete` and `reached_top_200_or_end=true`. Missing plans/nodes, false traversal flags or failed nodes prevent complete claims. Completeness refers only to declared paths and scan depth.

Ranking-date mismatches, invalid publication dates, missing required new-entry evidence, missing product IDs and unknown explicitly requested gender go to unresolved. Missing price, work IDs, optional apparel fields or links remain visible when required evidence is present.

## Product Semantics

Keep different product IDs separate even with similar pictures or titles. Account counts use distinct nonempty source accounts. Automatic trend scoring, similar-style matching, content analysis, SKU verification, profit estimation and merchant verification are not implemented.
