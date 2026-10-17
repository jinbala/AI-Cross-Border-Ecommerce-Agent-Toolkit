# Adapter And HTML Input Contract

The public skill contains methodology and a deterministic HTML renderer, not a private Data Compass scraper. A real deployment supplies an authorized browser/data adapter and may supply a storage adapter.

## Browser Or Data Adapter

The adapter should expose observable platform state and serial collection:

```text
select_identity(identity_name) -> observed_identity
open_ranking(ranking_name, period) -> page_state
select_category(category_path[]) -> observed_category_path
collect_to_top_200_or_end() -> node_collection
```

`page_state` should expose:

```text
observed_identity
platform
ranking_name
period
ranking_date
login_state
challenge_state
```

`node_collection` should expose:

```text
category_path[]
attempts
pages_collected
rows_collected
reached_top_200_or_end
status
failure_reason
relations[]
```

The adapter may use normal, authorized browser automation. It must not export session secrets, bypass access controls, or claim state it cannot read back.

## Renderer Input

### 商品榜输入（用户提供的 rank-product 入口）

The local tool defaults to product ranking. This separate schema does not manufacture graphic-post evidence:

```json
{
  "meta": {
    "source_type": "product_ranking",
    "ranking_name": "商品榜单",
    "ranking_date": "2026-10-12",
    "period": "填写源页面实际显示的统计周期；未知留空"
  },
  "products": [
    {
      "ranking_date": "2026-10-12",
      "category_path": ["填写实际来源类目"],
      "rank": 1,
      "product": {"id": "原始文本ID", "name": "商品名称", "price_min": 129, "apparel": {"gender": "女款"}},
      "metrics": {"transaction_amount": "原始展示值", "sales_count": "原始展示值"}
    }
  ]
}
```

Product mode applies date consistency, price and gender checks. `publication_days` and `require_new_entry` are not applied; `meta.publish_window=null` and `applied_filters` records the effective rules. There are no invented works, content-repetition signals or creator counts. Duplicate product/category observations retain their first copy; different category observations stay available under the product. Missing price stays pending.

CSV uses `裤装商品榜模板.csv`, requiring headers 榜单日期、商品ID、商品名称; work/date/new-entry headers are not required. Current headers are the tool's schema, not a claim about official exports. Actual source column mappings must be verified against the logged-in page/export. Sources are configured in `config/data-sources.json`; opening links alone does not import rows.

### Pants Local Tool

Windows: double-click `打开裤装选品.cmd`, or build with `node scripts/build_local_tool.mjs` and open `results/裤装选品工具.html`. The builder embeds `results/latest-compass-products.json` when it contains validated real product data; the page automatically renders it with identity, actual period and collection scope. The product snapshot normalizer CLI updates this cache and rebuilds the tool automatically. No user template filling or importing is needed for that workflow. Missing/broken caches show an explicit message without falling back to fictional demos. For other sources, manual CSV/JSON import remains in a collapsed optional section. Chinese CSV headers map to the equivalent JSON fields; class paths use `>` separators. CSV new-entry values accept true/false/是/否/1/0; empty means unknown. IDs must be strings, never numeric spreadsheet cells that have already lost precision.

An input may include `config` with `publication_days`, `price_floor`, `price_ceiling`, `require_new_entry`, `gender` and `timezone` (Asia/Shanghai). CLI `--config FILE` overrides input config; visual controls override it in the local tool. Defaults are 3 days, 0–1000 inclusive, required new entry, all genders. Unknown prices remain visible. Unknown explicitly requested gender is unresolved.

`config.price_basis` accepts `sku_min` (legacy CLI default) or `price_band` (explicit product UI default). Band mode checks inclusive range overlap from `price_band_display` or an explicitly labeled legacy price-band display; unrecognized text is never converted to a guessed number. It falls back to an available numeric SKU minimum and otherwise retains the unknown price with visible feedback. Source `price_min` remains unchanged. Exports include the effective basis and rule; the workbench supports both input/change events and an explicit apply button.

The local product workbench displays cards directly, with immediate gender/search/type filters, account-scoped browser favorites and view-specific CSV/HTML downloads. Unknown minimum SKU prices remain unknown. View exports retain source coverage and label the additional view filters; they do not claim complete platform collection. CSV cell text is escaped against spreadsheet formulas. Clipboard/storage failures leave visible fallbacks. `scripts/local_tool_app.js` contains interaction logic and `scripts/local_tool_shell.html` contains the layout; the builder bundles these into one offline HTML file.

Optional product extension:

```json
{
  "shop": "店铺名称",
  "price_sku": "价格对应的实际裤装SKU；未知留空",
  "apparel": {
    "gender": "女款",
    "type": "牛仔裤",
    "fit": "直筒",
    "fabric": "有依据的面料信息",
    "season": "春秋",
    "sizes": "S–XL"
  }
}
```

Do not infer these optional values from a similar product or generic description. Titles and images do not certify identical goods.

Set `meta.is_demo=true` for fictional inputs; the renderer displays a demo notice and suppresses generated work links. Real rows require their own `ranking_date` matching the task. Zoned publication timestamps are normalized to Shanghai time; date-only/local timestamps are business time. Raw source metrics retain their original display units.

Supply `expected_nodes` as exact category-path arrays. Coverage completion requires every expected path to have `status=complete` and `reached_top_200_or_end=true`, without failed nodes. Without a plan, coverage is unknown even when some rows were imported successfully. Complete means only the declared scan range.

`scripts/render_selection_html.mjs` accepts UTF-8 JSON:

```json
{
  "meta": {
    "ranking_date": "2026-08-20",
    "generated_at": "2026-08-21T09:00:00+08:00"
  },
  "coverage": [
    {
      "category_path": ["个护家清", "个人护理", "全部"],
      "status": "complete",
      "attempts": 1,
      "pages": 10,
      "rows": 200,
      "reached_top_200_or_end": true
    }
  ],
  "failed_nodes": [],
  "relations": [
    {
      "ranking_date": "2026-08-20",
      "category_path": ["个护家清", "个人护理", "身体清洁", "全部"],
      "rank": 12,
      "is_new": true,
      "product": {
        "id": "PRODUCT_ID",
        "name": "商品名称",
        "price_display": "¥99–¥129",
        "price_min": 99,
        "link": "https://haohuo.jinritemai.com/..."
      },
      "work": {
        "id": "WORK_ID",
        "title": "作品标题",
        "author": "作者昵称",
        "account": "作者账号",
        "published_at": "2026-08-19T12:36:00+08:00"
      },
      "metrics": {
        "transaction_amount": "¥2,500–¥5,000",
        "sales_count": "0–25",
        "views": "7.5万–10万",
        "likes": "100–250"
      }
    }
  ]
}
```

`ranking_date`, `category_path`, `rank`, `is_new`, `product.id`, `work.id`, and `work.published_at` must come from the source rather than inference. Missing optional display fields stay missing and are rendered as `待验证`.

`product.price_min` is the numeric lowest purchasable price. For a range, supply the lower bound. Use `null` when unreadable; the renderer keeps that product and marks the price for review.

## Renderer Output

```bash
node scripts/render_selection_html.mjs input.json --output-dir ./results
```

The script writes `商品榜选品-{ranking_date}.html` for product mode, or `选品结果-{ranking_date}-近{publication_days}日.html` for graphic mode. Use `--output FILE` for a chosen destination. `--config config/selection.json` selects this business's defaults explicitly.

The renderer:

- filters to the configured publication window ending on ranking date;
- requires `is_new=true` by default, unless explicitly disabled;
- applies configured inclusive price bounds and gender;
- deduplicates `(product.id, work.id)` and keeps the first category path;
- groups by product, computes repetition, and sorts deterministically;
- constructs Douyin links from work IDs without opening them;
- renders product links only when their URI scheme is HTTP or HTTPS; missing or unsafe schemes are marked `商品链接待验证` without excluding the relation;
- embeds all data, CSS, and JavaScript into one HTML file.

The local tool additionally downloads the built **report JSON** (`groups`, `summary`, `unresolved`), which is a processed artifact, not raw `relations` input. Retain the original CSV/JSON separately for re-filtering. No automatic history persistence or remote writes are performed.

## Storage Adapter

Storage is optional and runs only after explicit user authorization:

```text
write_raw(rows, idempotency_key) -> raw_write_result
write_candidates(rows, policy_name, idempotency_key) -> candidate_write_result
```

Results should expose `inserted_count`, `existing_count`, `failed_count`, and per-row failure reasons. The adopting project owns platform-specific fields and its candidate policy; this public skill keeps raw rows, user-list products, storage candidates, and recommendations semantically separate.

## Required Failure Behavior

- If identity cannot be read back, return `identity_unverified`.
- If ranking state is stale or mismatched, return observed and expected values.
- If a node stops early, return `reached_top_200_or_end=false` and a failure reason.
- Retry a healthy category node once; do not retry a platform-gate failure.
- If a write is partially successful, preserve the idempotency key and return per-row failures.
- Adapter exceptions must not be rephrased as zero matching products.

Keep credentials and raw session material inside the adapter's secure runtime. The skill receives only normalized business fields and safe diagnostics.
