#!/usr/bin/env python3
"""Contract tests for the pants skill package."""

from __future__ import annotations

import json
import unittest
import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTest(unittest.TestCase):
    def test_release_version_is_031(self) -> None:
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.3.1")

    def test_pants_catalog_uses_verified_leaf_paths_without_all_clothing_aggregate(self) -> None:
        catalog = json.loads(
            (ROOT / "references/category-catalog.yaml").read_text(encoding="utf-8")
        )
        anchors = {item["logical_name"]: item for item in catalog["anchors"]}

        self.assertEqual(set(anchors), {"男裤", "女裤"})
        self.assertTrue(catalog['source']['verified'])
        for anchor in anchors.values():
            self.assertEqual(anchor["third_level_categories"][0], "全部")
            self.assertTrue(anchor["verified"])
            self.assertFalse(anchor["include_aggregate"])
            self.assertEqual(anchor["path"][:2], ["服饰内衣", "服装"])
            for node in anchor['scan_nodes']:
                self.assertEqual(node[:-1], anchor['path'])
                self.assertIn(node[-1], anchor['third_level_categories'][1:])
                self.assertNotIn(node[-1], ['全部', 'T恤/Polo衫', '羽绒服'])

    def test_user_list_defaults_are_explicit_and_storage_mode_is_unchanged(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_phrases = (
            "publication_days",
            "最低可购买价",
            "¥1000",
            "category-catalog.yaml",
            "TOP200",
            "重复出现",
            "多作品出现",
            "高频出现",
            "选品结果-YYYY-MM-DD-近N日.html",
            "图文直接成交榜",
            "飞书",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, skill)

        self.assertIn("require_new_entry", skill)
        self.assertIn("https://www.douyin.com/video/{作品ID}", skill)
        self.assertIn("不打开验证", skill)

    def test_product_detail_collection_has_a_zero_residency_tab_budget(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        failure = (ROOT / "references/failure-handling.md").read_text(
            encoding="utf-8"
        )

        for phrase in (
            "zero-residency",
            "Normally keep one temporary product-detail tab",
            "at most three temporary product-detail tabs",
            "return to the pre-click tab baseline",
        ):
            self.assertIn(phrase, skill)
        self.assertIn("pause collection", failure)
        self.assertIn("temporary product-detail tabs", failure)

    def test_catalog_validator_supports_other_businesses_but_rejects_false_verification(self) -> None:
        spec = importlib.util.spec_from_file_location("validator", ROOT / "scripts/validate_skill.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            module.ROOT = Path(directory)
            (module.ROOT / "references").mkdir()
            path = module.ROOT / "references/category-catalog.yaml"
            item = {"logical_name": "自定义裤装", "path": [], "verified": False, "third_level_categories": ["全部"]}
            path.write_text(json.dumps({"anchors": [item]}), encoding="utf-8")
            errors = []
            module.validate_category_catalog(errors)
            self.assertEqual(errors, [])
            item["verified"] = True
            path.write_text(json.dumps({"anchors": [item]}), encoding="utf-8")
            module.validate_category_catalog(errors)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
