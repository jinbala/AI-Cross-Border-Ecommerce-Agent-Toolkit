# Changelog

## Unreleased

- Fixed category-dependent Compass price options: wait for the selected category, use the official custom-price dialog when a preset differs, verify saved bounds and preserve query mode in source evidence. Regression fixtures now use different price bands for women's and men's categories.
- Reorganized the desktop into four sidebar destinations and wired startup/background updates, sign-in continuation, progress, cancellation and the latest queued price choice.
- Added multi-select source price bands, disjoint custom ranges, saved price combinations and OR filtering. Source bands are queried independently with per-query rank evidence and deduplicated product cards.
- Added automatic category/page traversal with atomic batch saves, preserved filters on refresh and distinguished explicit empty rankings from failed reads; exercised the full flow in WebView2 fixtures.

- Added an in-app Compass login/browser and current-page collection, with persistent app-owned sign-in, actual title-navigation URL capture and atomic local saves. Daily desktop use no longer needs Codex or an Edge extension.
- Shared strict browser-compatible snapshot normalization with the desktop, replacing reread pages and starting a fresh collection for account/period changes; added a real WebView2 collector fixture check.

- Restored the authorized Edge connection and captured all 20 trial products' actual URLs through title clicks; updated saved data, the desktop assets and the portable package.

- Fixed price filtering for real Compass records with price bands and unknown SKU minima; the product UI now defaults to interval overlap against page bands with explicit rule/count feedback.
- Added native change-event coverage, preserved selected pants types across combined filters, and extended the actual desktop check to apply/reset price filters.

- Made captured product URLs clickable on titles in both the workbench and exported HTML, and displayed source price bands with a separate label.
- Corrected the collection rule: disabled detail buttons do not establish title-link availability; title navigation must be checked through normal UI interaction.

- Moved available product links onto cards, made unavailable links explicit, and added product-name/ID copy actions with clipboard fallback.

- Added a native Windows desktop host using WebView2, with desktop/start-menu shortcuts, persistent app storage, native save dialogs and automatic loading of locally updated data.
- Added reproducible desktop build/install scripts, a portable package and a real WebView2 rendering/storage/download smoke check.

- Replaced the product preview iframe with a direct workbench: quick male/female selection, immediate search/type filters, favorites and filtered CSV/HTML exports.
- Moved advanced controls out of the main flow; added a copyable collection instruction with clipboard fallback and explicit saved-data scope.

- Made saved real Compass data load and render automatically on opening the tool; moved templates/import/demo to an optional section.
- Snapshot normalization now updates the saved ranking and rebuilds the tool, removing manual import from the live-capture workflow.

- Connected the authorized Edge session and captured 20 real product-ranking rows across two pants categories, explicitly marked partial.
- Added a visible-DOM snapshot reader and strict normalizer preserving payment/click ranges, IDs, unknown SKU prices and unavailable links.
- Verified exact male/female pants menu paths; reports now retain full category paths and show trial scope and source-specific metrics.

## 0.3.1 - 2026-10-13

- Saved the four user-provided Data Compass entry URLs and exposed them in the local tool.
- Added a separate product-ranking import/report mode without graphic publication/new-entry requirements or fabricated content signals.
- Defaulted the local tool to product mode, retaining explicit graphic mode and source-aware CSV templates.
- Actual page fields, export support and live collection remain unverified without a connected logged-in browser.

## 0.3.0 - 2026-10-13

- Adapted the default workflow to men's and women's pants; preserved the legacy catalog and marked real platform paths unverified.
- Added an offline CSV/JSON import tool and Windows launcher, with configurable publication window, price range and gender.
- Shared renderer logic between CLI and local tool; added apparel filters, known-account counts and neutral repetition labels.
- Added ranking-date checks, Shanghai time normalization, explicit coverage evidence and labeled demos without fabricated work links.
- Added pants-specific behavior evaluations and regression checks for import and browser-side scripts.

## 0.2.1 - 2026-08-21

- Added a zero-residency product-detail tab budget so full-category collection cannot accumulate browser tabs.
- Balanced throughput and stability around one normal temporary tab with a hard ceiling of three.
- Required immediate cleanup and baseline verification before processing the next product.
- Added an evaluation and contract coverage for low-memory continuation after tab leakage.

## 0.2.0 - 2026-08-21

- Added a fixed, user-approved fine-category catalog for the five default business anchors.
- Changed user-list freshness to the latest completed ranking plus a three-date publication window.
- Made lowest purchasable price above ¥1000 the only implicit business exclusion.
- Added product grouping, current-run repetition tiers, best-rank representatives, and deterministic sorting.
- Changed work-link handling to deterministic construction from work IDs without validity checks.
- Added a standalone warehouse-audit HTML generator with coverage and repetition views.
- Preserved adopting-project storage and Feishu candidate policies as an explicitly authorized separate mode.

## 0.1.0 - 2026-08-19

- Published the initial portable Data Compass discovery skill.
