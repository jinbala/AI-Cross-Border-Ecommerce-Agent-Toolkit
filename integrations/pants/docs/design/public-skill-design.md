# Product Selection Specialist Public Skill Design

Historical v0.2 design. The active v0.3 pants workflow, local tool and unverified category setup are documented in README.md, SKILL.md and references/adapter-contract.md.

## Goal

Publish a reusable, installable skill that teaches an AI agent how to perform broad, evidence-based product discovery from Data Compass, surface repeatable product/content opportunities, and deliver a directly usable HTML audit page without exposing the owner's private automation system.

## Scope

The public skill covers the discovery stage:

1. Confirm the intended browser identity and ranking context.
2. Load a fixed, user-approved catalog for five business anchors and their fine-grained category nodes.
3. Scan the latest completed graphic ranking serially to TOP200 or a proven end.
4. Filter its works to the ranking date and preceding two dates with explicit new-entry evidence.
5. Exclude only products whose lowest purchasable price is greater than ¥1000.
6. Group by product ID, expose every work, and tier current-run repetition.
7. Keep product links and deterministically constructed Douyin links separate.
8. Generate a standalone warehouse-audit HTML artifact.
9. Optionally hand rows to an external storage adapter whose policy remains separate.
10. Stop before product verification, scoring, or business outreach.

It does not include private browser profiles, credentials, Feishu identifiers, server addresses, internal CLI commands, private selectors, or platform API implementations.

## Package Structure

- `SKILL.md`: Triggering rules, workflow, safety boundaries, and response contract.
- `README.md`: Installation, usage, examples, and integration overview.
- `references/workflow.md`: Detailed discovery and filtering semantics.
- `references/adapter-contract.md`: Generic interface for browser and storage adapters.
- `references/category-catalog.yaml`: Fixed five-anchor scan catalog and update policy.
- `references/failure-handling.md`: Fail-closed behavior and user-facing explanations.
- `evals/evals.json`: Realistic prompts and expected behavior.
- `scripts/render_selection_html.mjs`: Deterministic grouping and standalone HTML generator.
- `scripts/validate_skill.py`: Standard-library validation and sensitive-data checks.
- `LICENSE`: MIT License.

## Portability Strategy

The skill describes capabilities instead of hard-coding one repository's commands. An adopting project supplies adapters for page collection and optional storage. The category catalog, normalized renderer input, and HTML generator are portable. If a required adapter is unavailable, the skill reports the missing capability rather than pretending it executed the workflow.

## Security And Privacy

- Never export cookies, tokens, passwords, browser profiles, or private request headers.
- Never bypass CAPTCHA, login controls, rate limits, or platform risk controls.
- Never infer product identity from an ambiguous result.
- Never perform business actions such as adding products, requesting samples, or contacting merchants.
- Treat evidence insufficiency as a valid outcome.

## Acceptance Criteria

- The repository can be installed by copying one directory into an agent skill directory.
- No absolute personal paths or private project identifiers remain.
- The skill distinguishes ranking date from the three-date publication window.
- Every user-list result requires the platform's new-entry signal.
- The only implicit business exclusion is lowest purchasable price greater than ¥1000.
- Fixed fine-category nodes do not get rediscovered during normal runs.
- Full-result requests do not silently become Top-N lists.
- Product and content links remain separate and content links are not opened for validation.
- Repetition, representatives, and ties are deterministic.
- The generated HTML includes coverage, unresolved rows, a repetition radar, grouped products, all works, filters, and direct links.
- Validation passes locally and the repository is publicly accessible on GitHub.
