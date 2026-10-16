import csv
import json
from pathlib import Path
import tempfile
import unittest

from desktop_app import core, selection

BUILD = Path(__file__).resolve().parents[1] / ".build/tests"
BUILD.mkdir(parents=True, exist_ok=True)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BUILD)
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def load(self, headers, rows):
        path = self.path / "input.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return selection.read_csv(path, as_of="2026-10-16", platform="Amazon", market="US", currency="USD")

    def test_factory_filter_distinguishes_missing_zero_and_failure(self):
        data = self.load(["ASIN", "标题", "月销量(父)", "评分"], [
            ["A1", "改进款", 1200, 3.2], ["A2", "缺资料", 1300, ""], ["A3", "不符", 400, 4.8], ["A4", "零销量", 0, 3]])
        result = selection.screen(data, "factory_upgrade")
        self.assertEqual([r["status"] for r in result["results"]], ["符合筛选", "资料待补", "不符合", "不符合"])
        self.assertEqual(result["results"][1]["missing"], ["评分"])
        self.assertEqual(result["counts"]["不符合"], 2)

    def test_dates_use_snapshot_and_reject_future(self):
        data = self.load(["ASIN", "上架日期", "月销量", "月销量增长率"], [["A", "2026-10-01", 300, "12%"]])
        self.assertEqual(data["records"][0]["age_days"], 15)
        self.assertEqual(selection.screen(data, "new_product")["results"][0]["status"], "符合筛选")
        with self.assertRaisesRegex(ValueError, "晚于"):
            self.load(["ASIN", "上架日期"], [["A", "2026-11-01"]])

    def test_duplicate_ids_keep_first_row(self):
        data = self.load(["ASIN", "月销量", "评分"], [["A", 1200, 3], ["A", 200, 5]])
        self.assertEqual(data["meta"]["duplicates"], 1)
        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["records"][0]["monthly_sales"], 1200)

    def test_percent_units_and_negative_growth(self):
        self.assertEqual(selection.metric("10%"), 10)
        self.assertEqual(selection.metric("0.1"), .1)
        self.assertEqual(selection.metric("-12%", allow_negative=True), -12)
        data = self.load(["ASIN", "月销量", "月销量增长率", "上架天数"], [["A", 300, "-10%", 30]])
        self.assertEqual(selection.screen(data, "new_product")["results"][0]["status"], "不符合")

    def test_invalid_values_and_threshold_bounds(self):
        for raw in ("nan", "inf", "-1", "xxx"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                selection.metric(raw)
        with self.assertRaisesRegex(ValueError, "不能超过"):
            self.load(["ASIN", "评分"], [["A", 6]])
        with self.assertRaisesRegex(ValueError, "下限"):
            selection.thresholds("rising_search", {"search_rank>=": 100000, "search_rank<=": 10000})

    def test_keyword_word_count_and_chinese_unknown(self):
        data = self.load(["关键词", "月搜索量"], [["women cotton summer shirt", 1000], ["女式夏季衬衫", 1000]])
        result = selection.screen(data, "long_tail")
        self.assertEqual(result["results"][0]["status"], "符合筛选")
        self.assertEqual(result["results"][1]["status"], "资料待补")

    def test_click_cost_ratio_is_not_acos(self):
        data = self.load(["关键词", "PPC", "商品均价"], [["cotton shirt", ".5", 20], ["linen shirt", 1, 0]])
        result = selection.screen(data, "traffic_cost")
        self.assertEqual(result["results"][0]["record"]["traffic_ratio"], 2.5)
        self.assertEqual(result["results"][1]["status"], "资料待补")
        self.assertIn("不是 ACoS", selection.STRATEGIES["traffic_cost"]["next"])

    def test_decimal_bids_and_grouped_integer_counts(self):
        data = self.load(["ASIN", "月销量", "PPC", "商品均价"], [["A", "1.234", "0.005", "1.234"]])
        self.assertEqual(data["records"][0]["monthly_sales"], 1234)
        self.assertEqual(data["records"][0]["ppc"], .005)
        self.assertEqual(data["records"][0]["average_price"], 1.234)
        self.assertEqual(selection.metric("12,345%"), 12.345)
        self.assertEqual(selection.metric(.005), .005)

    def test_all_strategies_can_render_missing_evidence(self):
        data = self.load(["ASIN", "标题"], [["A", "测试款"]])
        for strategy in selection.STRATEGIES:
            with self.subTest(strategy=strategy):
                result = selection.screen(data, strategy)
                self.assertEqual(result["results"][0]["status"], "资料待补")
                self.assertIn("目标平台", selection.report(result))

    def test_candidate_backup_and_v1_restore_compatibility(self):
        data = self.load(["ASIN", "月销量", "评分"], [["A", 1200, 3]])
        screened = selection.screen(data, "factory_upgrade")
        item = selection.candidate(screened, screened["results"][0])
        store = core.Store(self.path / "store")
        try:
            candidate_id = store.save("candidate", item)
            path = self.path / "backup.json"
            store.backup(path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], 2)
            store.delete(candidate_id)
            store.restore(path)
            self.assertEqual(store.get(candidate_id)["evidence"]["monthly_sales"], 1200)
            self.assertIn("不替人批准采购", selection.review_brief(store.get(candidate_id)))
            core.atomic_json(path, {"format": "garment-workbench", "version": 1, "records": {"product": [{"id": "old-product", "name": "旧版款"}]}})
            store.restore(path)
            self.assertEqual(len(store.list("candidate")), 1)
            self.assertEqual(store.get("old-product")["name"], "旧版款")
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
