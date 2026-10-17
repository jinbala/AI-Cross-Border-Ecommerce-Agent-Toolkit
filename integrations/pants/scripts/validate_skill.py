#!/usr/bin/env python3
"""Validate the public skill package without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "VERSION",
    "CHANGELOG.md",
    "LICENSE",
    "evals/evals.json",
    "references/workflow.md",
    "references/adapter-contract.md",
    "references/category-catalog.yaml",
    "references/failure-handling.md",
    "scripts/render_selection_html.mjs",
    "scripts/selection_core.mjs",
    "scripts/import_selection.mjs",
    "scripts/build_local_tool.mjs",
    "scripts/local_tool_app.js",
    "scripts/local_tool_shell.html",
    "desktop/PantsWorkbench.cs",
    "desktop/README.md",
    "scripts/build_desktop.ps1",
    "scripts/install_desktop.ps1",
    "scripts/capture_compass_product.mjs",
    "scripts/normalize_compass_snapshot.mjs",
    "scripts/compass_core.mjs",
    "desktop/CompassPanel.cs",
    "desktop/CompassUpdater.cs",
    "desktop/WorkbenchNavigation.cs",
    "scripts/compass_navigation.mjs",
    "scripts/price_ranges.mjs",
    "config/selection.json",
    "config/data-sources.json",
    "tests/fixtures/pants-demo.json",
    "tests/fixtures/product-ranking-demo.json",
    "tests/fixtures/compass-desktop.html",
    "tests/fixtures/compass-update.html",
    "tests/render_selection_html.test.mjs",
    "tests/test_skill_contract.py",
)
TEXT_SUFFIXES = {".md", ".json", ".mjs", ".js", ".html", ".cs", ".ps1", ".config", ".manifest", ".py", ".txt", ".yaml", ".yml"}

FORBIDDEN_PATTERNS = {
    "personal macOS path": re.compile("/" + r"Users/[^/\s]+/"),
    "personal Windows path": re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+\\\\"),
    "IPv4 address": re.compile(
        r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
        r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
    ),
    "credential assignment": re.compile(
        r"(?im)^\s*(?:password|passwd|cookie|token|app_?secret|secret_?key)\s*[:=]\s*\S+"
    ),
    "private browser profile": re.compile(r"(?i)(?:chrome|browser)[ _-]?profile\s*[:=]\s*[/~]"),
}


def iter_text_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.relative_to(ROOT).parts[0] not in {"results", "dist"}
        and path.suffix.lower() in TEXT_SUFFIXES
    ]


def validate_required_files(errors: list[str]) -> None:
    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).is_file():
            errors.append(f"missing required file: {relative_path}")


def validate_skill(errors: list[str]) -> None:
    path = ROOT / "SKILL.md"
    if not path.is_file():
        return

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 500:
        errors.append(f"SKILL.md exceeds 500 lines: {len(lines)}")

    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        errors.append("SKILL.md has no valid YAML frontmatter block")
        return

    frontmatter = match.group(1)
    for key in ("name", "description"):
        if not re.search(rf"(?m)^{key}:\s*\S.+$", frontmatter):
            errors.append(f"SKILL.md frontmatter is missing {key}")

    if not re.search(r"(?m)^name:\s*product-selection-specialist\s*$", frontmatter):
        errors.append("SKILL.md name must be product-selection-specialist")


def validate_evals(errors: list[str]) -> None:
    path = ROOT / "evals/evals.json"
    if not path.is_file():
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"evals/evals.json is invalid JSON: {exc}")
        return

    if data.get("skill_name") != "product-selection-specialist":
        errors.append("evals skill_name does not match the skill")

    evals = data.get("evals")
    if not isinstance(evals, list) or len(evals) < 15:
        errors.append("evals/evals.json must contain at least 15 evals")
        return

    seen_ids: set[object] = set()
    for index, item in enumerate(evals, start=1):
        if not isinstance(item, dict):
            errors.append(f"eval {index} is not an object")
            continue
        eval_id = item.get("id")
        if eval_id in seen_ids:
            errors.append(f"duplicate eval id: {eval_id}")
        seen_ids.add(eval_id)
        for key in ("prompt", "expected_output"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                errors.append(f"eval {eval_id!r} has no {key}")
        expectations = item.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            errors.append(f"eval {eval_id!r} has no expectations")


def validate_version(errors: list[str]) -> None:
    path = ROOT / "VERSION"
    if path.is_file() and not re.fullmatch(r"\d+\.\d+\.\d+", path.read_text(encoding="utf-8").strip()):
        errors.append("VERSION must be a semantic version")


def validate_category_catalog(errors: list[str]) -> None:
    path = ROOT / "references/category-catalog.yaml"
    if not path.is_file():
        return
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"category-catalog.yaml must be JSON-compatible YAML: {exc}")
        return

    anchors = catalog.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        errors.append("category catalog anchors must be a nonempty list")
        return
    seen_names: set[str] = set()
    for item in anchors:
        if not isinstance(item, dict):
            errors.append("catalog anchor must be an object")
            continue
        name = item.get("logical_name")
        if not isinstance(name, str) or not name.strip() or name in seen_names:
            errors.append("catalog logical_name must be nonempty and unique")
        else:
            seen_names.add(name)
        path_value = item.get("path")
        verified = item.get("verified")
        if not isinstance(verified, bool):
            errors.append(f"category {name!r} must declare verified boolean")
        if not isinstance(path_value, list) or any(not isinstance(part, str) or not part.strip() for part in path_value):
            errors.append(f"category {name!r} path must be a string array")
        elif verified and not path_value:
            errors.append(f"category {name!r} cannot be verified with an empty path")
        categories = item.get("third_level_categories")
        if not isinstance(categories, list) or not categories or categories[0] != "全部":
            errors.append(
                f"category {item.get('logical_name')!r} must begin with the aggregate 全部 node"
            )
        elif any(not isinstance(part, str) or not part.strip() for part in categories) or len(categories) != len(set(categories)):
            errors.append(f"category {name!r} has invalid or duplicate nodes")
        scan_nodes = item.get("scan_nodes")
        if scan_nodes is not None:
            if not isinstance(scan_nodes, list) or not scan_nodes:
                errors.append(f"category {name!r} scan_nodes must be a nonempty list")
            else:
                seen_nodes = set()
                for node in scan_nodes:
                    if not isinstance(node, list) or not node or any(not isinstance(part, str) or not part.strip() for part in node):
                        errors.append(f"category {name!r} has invalid scan node")
                        continue
                    if not isinstance(path_value, list) or node[:-1] != path_value:
                        errors.append(f"category {name!r} scan node must extend its anchor path")
                    if item.get("include_aggregate") is False and node[-1] == "全部":
                        errors.append(f"category {name!r} must not scan aggregate nodes")
                    key = tuple(node)
                    if key in seen_nodes:
                        errors.append(f"category {name!r} has duplicate scan nodes")
                    seen_nodes.add(key)


def scan_sensitive_content(errors: list[str]) -> None:
    for path in iter_text_files():
        relative_path = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8-sig")
        for label, pattern in FORBIDDEN_PATTERNS.items():
            candidate = text
            if label == "IPv4 address" and path.suffix == ".manifest":
                candidate = re.sub(r'\bversion="\d+(?:\.\d+){3}"', 'version=""', candidate)
            if pattern.search(candidate):
                errors.append(f"{relative_path}: contains {label}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    validate_skill(errors)
    validate_evals(errors)
    validate_version(errors)
    validate_category_catalog(errors)
    scan_sensitive_content(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
