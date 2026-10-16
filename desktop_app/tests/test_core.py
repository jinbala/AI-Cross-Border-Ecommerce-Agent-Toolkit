from contextlib import redirect_stderr
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from desktop_app import core

BUILD = Path(__file__).resolve().parents[1] / ".build" / "tests"
BUILD.mkdir(parents=True, exist_ok=True)


class PricingTests(unittest.TestCase):
    def test_supply_margin_and_batch(self):
        r = core.calculate_pricing(dict(price=30, production=18, packaging=1, inbound=1, loss=2, quantity=100, target=20))
        self.assertEqual(r["unit_profit"], 8)
        self.assertEqual(r["batch_profit"], 800)
        self.assertEqual(r["target_price"], 27.5)
        self.assertEqual(r["break_even"], 22)

    def test_retail_all_fees(self):
        r = core.calculate_pricing(dict(price=100, production=30, packaging=2, inbound=3, shipping=5, other=2, loss=3,
                                        commission=10, tax=5, advertising=10, quantity=20, target=20))
        self.assertEqual(r["unit_cost"], 45)
        self.assertEqual(r["unit_profit"], 30)
        self.assertEqual(r["margin"], 30)
        self.assertEqual(r["break_even"], 60)
        self.assertEqual(r["target_price"], 81.82)
        self.assertEqual(r["ad_roas"], 2.5)

    def test_price_rounds_up_to_reach_target(self):
        r = core.calculate_pricing(dict(price=10, production=1, commission=3, target=17))
        self.assertEqual(r["break_even"], 1.04)
        self.assertGreaterEqual(Decimal(str(r["target_price"])) * Decimal(".80"), 1)

    def test_zero_and_loss(self):
        r = core.calculate_pricing(dict(price=0, production=20))
        self.assertIsNone(r["margin"])
        self.assertEqual(r["unit_profit"], -20)
        self.assertIsNone(r["ad_roas"])

    def test_reject_invalid_and_non_finite(self):
        for values in [dict(price="nan"), dict(price="Infinity"), dict(price=-1), dict(quantity=1.5),
                       dict(quantity=0), dict(commission=70, tax=30), dict(target=90, commission=20), dict(price="abc")]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                core.calculate_pricing(values)

    def test_currency_and_snapshot(self):
        v = dict(price=30, production=20, currency="USD", mode="自营零售")
        report = core.pricing_report(v, core.calculate_pricing(v))
        self.assertIn("USD", report)
        self.assertIn('"production": 20', report)
        self.assertIn("预留", report)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BUILD)
        self.path = Path(self.temp.name)
        self.store = core.Store(self.path / "data")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_persist_update_delete(self):
        record_id = self.store.save("product", {"name": "测试衬衫", "cost": "18"})
        self.store.save("product", {"name": "改版衬衫", "cost": "20"}, record_id)
        self.assertEqual(len(self.store.list("product")), 1)
        self.assertEqual(self.store.get(record_id)["cost"], "20")
        self.store.close()
        self.store = core.Store(self.path / "data")
        self.assertEqual(self.store.get(record_id)["name"], "改版衬衫")
        self.store.delete(record_id)
        self.assertEqual(self.store.list("product"), [])

    def test_backup_excludes_key_and_restores_by_id(self):
        self.store.set_setting("api_key", "not-a-real-secret")
        self.store.set_setting("api_base", "https://example.test/v1")
        record_id = self.store.save("product", {"name": "款式甲", "cost": "20"})
        self.store.save("artifact", {"name": "文案", "kind": "文字", "content": "真实文字"})
        self.store.save("experiment", {"name": "试验", "spent": 100, "revenue": 150, "budget": 200})
        backup = self.path / "backup.json"
        self.store.backup(backup)
        self.assertNotIn("not-a-real-secret", backup.read_text(encoding="utf-8"))
        self.assertNotIn("api_base", backup.read_text(encoding="utf-8"))
        self.store.save("product", {"name": "变更"}, record_id)
        self.assertEqual(self.store.restore(backup), 3)
        self.assertEqual(len(self.store.list("product")), 1)
        self.assertEqual(self.store.get(record_id)["name"], "款式甲")

    def test_restore_validates_every_record_before_mutation(self):
        self.store.save("product", {"name": "保留"})
        payload = {"format": "garment-workbench", "version": 1, "records": {
            "product": [{"id": "new", "name": "不应导入"}],
            "experiment": [{"id": "bad", "name": "错误", "spent": "nan"}]}}
        backup = self.path / "bad.json"
        core.atomic_json(backup, payload)
        with self.assertRaises(ValueError):
            self.store.restore(backup)
        self.assertEqual([r["name"] for r in self.store.list("product")], ["保留"])

    def test_restore_rejects_conflicting_types(self):
        record_id = self.store.save("product", {"name": "保留"})
        backup = self.path / "bad.json"
        core.atomic_json(backup, {"format": "garment-workbench", "version": 1, "records": {
            "artifact": [{"id": record_id, "name": "不能覆盖", "content": "text"}]}})
        with self.assertRaises(ValueError):
            self.store.restore(backup)
        self.assertEqual(self.store.get(record_id)["name"], "保留")


class WorkflowAndAnalyticsTests(unittest.TestCase):
    def test_all_seven_have_prompts_and_templates(self):
        for i, module in enumerate(core.MODULES):
            with self.subTest(module=module[1]):
                prompt = core.workflow_prompt(i, {"name": "测试衬衫", "fabric": "棉 100%"}, "供货 / 批发", "中国", "请检查缺项")
                self.assertIn("测试衬衫", prompt)
                self.assertIn("# 项目参考流程", prompt)
                self.assertIn("不得编造", prompt)
                self.assertGreater(len(core.workflow_template(i)), 100)

    def test_market_sample_and_currency(self):
        path = core.ROOT / "Agents/01_Market_Research_Agent/samples/sample_patinete_eletrico.csv"
        with redirect_stderr(io.StringIO()):
            report = core.market_report(path, "CNY")
        self.assertIn("CNY", report)
        self.assertNotIn("R$", report)
        self.assertIn("50", report)
        self.assertIn("74.1", report)

    def test_market_missing_column(self):
        with tempfile.TemporaryDirectory(dir=BUILD) as folder:
            path = Path(folder) / "input.csv"
            path.write_text("name,count\nshirt,3\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "未识别"):
                core.market_report(path)

    def test_import_numbers_match_documented_locale_formats(self):
        parser = core.load_agent_script(core.MODULES[0][2], "shaduola_parser")
        for raw, expected in [("19,90", 19.9), ("1,5", 1.5), ("1.234", 1234),
                              ("1.234.567", 1234567), ("R$ 1.234,56", 1234.56),
                              ("1,234.56", 1234.56), ("1.2万", 12000), ("1.234万", 12340)]:
            with self.subTest(raw=raw):
                self.assertAlmostEqual(parser._to_number(raw), expected)

    def test_ad_metrics(self):
        report = core.ad_report(dict(impressions=10000, clicks=200, orders=10, spend=100, revenue=500, unit_profit=15))
        self.assertIn("2.00%", report)
        self.assertIn("5.00%", report)
        self.assertIn("50.00", report)
        self.assertIn("3.33", report)

    def test_ad_no_orders_and_invalid_counts(self):
        report = core.ad_report(dict(impressions=100, clicks=10, spend=20))
        self.assertIn("样本偏少", report)
        self.assertIn("无订单", report)
        with self.assertRaises(ValueError):
            core.ad_report(dict(impressions=100, clicks=101, spend=1))


class AiAndCredentialTests(unittest.TestCase):
    def test_url_validation(self):
        self.assertEqual(core.api_url("https://example.test/v1/"), "https://example.test/v1/chat/completions")
        self.assertEqual(core.api_url("http://127.0.0.1:1234/v1"), "http://127.0.0.1:1234/v1/chat/completions")
        for url in ["http://example.test/v1", "file:///x", "https://key@example.test", "https://example.test?key=secret"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                core.api_url(url)

    @unittest.skipUnless(core.sys.platform == "win32", "Windows DPAPI")
    def test_dpapi_roundtrip(self):
        encrypted = core.protect_key("test-only-密钥")
        self.assertNotIn("test-only", encrypted)
        self.assertEqual(core.unprotect_key(encrypted), "test-only-密钥")
        self.assertEqual(core.unprotect_key("broken"), "")

    def test_mocked_ai_protocol(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({"choices": [{"message": {"content": "测试结果"}}]}).encode()
        with patch("desktop_app.core.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = Response()
            result = core.call_ai("https://example.test/v1", "fake-test-key", "test-model", "测试资料")
            self.assertEqual(result, "测试结果")
            request = opener.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(body["model"], "test-model")
            self.assertEqual(body["messages"][1]["content"], "测试资料")
            self.assertEqual(request.get_header("Authorization"), "Bearer fake-test-key")

    def test_http_errors_do_not_leak_response_secrets(self):
        with patch("desktop_app.core.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = urllib.error.HTTPError("https://example.test", 401, "private", {}, None)
            with self.assertRaisesRegex(ValueError, "401") as exc:
                core.call_ai("https://example.test", "fake", "test", "prompt")
            self.assertNotIn("private", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
