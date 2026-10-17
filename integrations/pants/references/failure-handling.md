# Failure Handling

## Local Import And Configuration

Local files do not require live-platform gates. Invalid CSV quoting/headers/column counts, malformed JSON, invalid configuration or a missing raw `relations` array stop report generation with a visible error. Clear previous preview/download state on file changes and errors so old results are not mistaken for new ones.

Rows with mismatched/missing ranking dates, invalid publication time or unknown explicitly requested gender enter unresolved. Do not relabel dates, fill source evidence or infer apparel attributes to force results. Missing planned coverage remains unknown/incomplete.

## Platform-Level Stops

Stop the whole run immediately when any shared gate fails:

- intended Data Compass browser/profile identity cannot be read back;
- source is not Data Compass;
- login, CAPTCHA, permission, request-frequency, or risk-control barrier appears;
- selected ranking does not match the intended source (`图文直接成交榜` in graphic mode, visible 商品榜单 at rank-product in product mode);
- actual period differs from the requested period (`近1天` for the default graphic run; no forced period for product mode);
- ranking date/range does not match the selected source context (latest completed date for default graphic mode);
- the shared browser/profile is under simultaneous control.

Report expected and observed state. Do not continue to later category nodes and do not convert the failure to a zero-result report.

## Category-Node Failures

When the shared platform gate remains healthy, retry a failed configured node once. After two total attempts:

1. record path, attempts, collected pages/rows, and failure reason;
2. mark overall coverage incomplete;
3. continue to the next configured node serially;
4. preserve every qualified relation already collected.

A missing category entry, unstable rows, or an early pagination stop is a node failure, not proof of no products.

## Temporary Product-Tab Cleanup

Product-detail capture must return to the pre-click open-tab baseline before the next product is processed. The normal target is one temporary tab and the hard limit is three. If temporary product-detail tabs remain, appear after the first cleanup pass, exceed the three-tab budget, or cannot be closed:

1. pause collection immediately;
2. enumerate only the temporary product-detail tabs created by the current capture action;
3. close them and verify the baseline again;
4. retry the current relation once only after the baseline is restored;
5. otherwise record the relation as unresolved and treat repeated tab leakage as a category-node failure.

Never solve tab leakage by opening more pages, closing unrelated user tabs, or continuing the batch with accumulated detail pages.

## Unresolved Relations

Do not place a relation in the qualified product list when publication time is missing/unreadable or new-entry evidence is absent. Preserve the safe identifying fields in the unresolved ledger and count them in the summary.

Missing price, work ID, product link, or display metrics does not by itself exclude an otherwise qualified relation. Mark the field `待验证`.

## Stale Ranking

Report both dates and stop:

```text
Expected latest ranking: YYYY-MM-DD
Observed ranking: YYYY-MM-DD
Result: platform gate failed; no user-list artifact or storage write was produced
```

Do not substitute an older ranking or collect three historical ranking dates.

## Incomplete Coverage

Report:

- configured node count, completed node count, missing/unproven nodes and failed node count;
- attempts and reason for every failed node;
- source relation count, qualified relation count, and unique product count;
- explicit statement `覆盖不完整，不能宣称平台全量`.

## Storage Problems

Storage mode preserves the adopting project's existing checkpoint and idempotency behavior. Report inserted, existing, and failed rows; never rerun collection merely to hide a partial write.

## Quantity Shortfall

A requested quantity is a target, not permission to relax category, date, new-entry, or price rules. Report the actual count and filtering breakdown. Never backfill from another date, ranking, category, or previous HTML file.
