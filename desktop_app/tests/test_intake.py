from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from desktop_app import core, selection, tabular

BUILD = Path(__file__).resolve().parents[1] / ".build/tests"
BUILD.mkdir(parents=True, exist_ok=True)


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BUILD)
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_names_work_without_metrics_or_market(self):
        result = selection.prepare_text("亚麻衬衫\n休闲裤\n亚麻衬衫")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["counts"]["资料待补"], 2)
        self.assertEqual(result["strategy"], "manual_lead")
        self.assertIsNone(result["results"][0]["record"]["monthly_sales"])

    def test_links_extract_only_known_identifiers(self):
        result = selection.prepare_text("https://www.amazon.com/dp/B012345678?ref=abc&token=private\nhttps://amazon.evil.test/dp/B012345678")
        first = selection.candidate(result, result["results"][0])
        second = selection.candidate(result, result["results"][1])
        self.assertEqual(first["source_id"], "B012345678")
        self.assertEqual(first["platform"], "Amazon")
        self.assertNotIn("private", first["evidence"]["source_url"])
        self.assertNotIn("private", str(first))
        self.assertEqual(second["source_id"], "")
        self.assertEqual(first["status"], "资料待补")

    def test_url_and_plain_asin_deduplicate(self):
        result = selection.prepare_text("B012345678\nhttps://www.amazon.com/dp/B012345678?ref=abc")
        self.assertEqual(len(result["results"]), 1)

    def test_pasted_excel_table_needs_no_csv_file(self):
        text = "导出说明\nASIN\t标题\t月销量\t评分\nA1\t衬衫\t1200\t3.2\n"
        result = selection.prepare_text(text, as_of="2026-10-16", platform="Amazon", market="US", currency="USD")
        self.assertEqual(result["strategy"], "factory_upgrade")
        self.assertEqual(result["counts"]["符合筛选"], 1)

    def test_table_unknown_scope_stays_pending(self):
        result = selection.prepare_text("ASIN\t月销量\t评分\nA1\t1200\t3.2")
        self.assertEqual(result["counts"]["资料待补"], 1)
        self.assertIn("数据市场", result["results"][0]["missing"])

    def test_table_requires_header_but_free_text_is_valid(self):
        with self.assertRaisesRegex(ValueError, "列名"):
            selection.prepare_text("A1\t衬衫\t1200\t3.2")
        self.assertEqual(selection.prepare_text("一款想开发的衬衫")["strategy"], "manual_lead")

    def test_excel_direct_import_handles_dates_percent_and_title_rows(self):
        excel = tabular.excel_module()
        book = excel.Workbook()
        empty = book.active
        empty.title = "说明"
        empty.append(["这页没有数据"])
        sheet = book.create_sheet("产品导出")
        sheet.append(["卖家精灵导出记录"])
        sheet.append(["ASIN", "标题", "月销量", "评分", "月销量增长率", "上架日期"])
        sheet.append(["XLSX-1", "Excel 衬衫", 300, 3.2, .12, datetime(2026, 10, 1)])
        sheet["E3"].number_format = "0.0%"
        sheet["F3"].number_format = "yyyy-mm-dd"
        path = self.path / "data.xlsx"
        book.save(path)
        book.close()
        data = selection.read_csv(path, as_of="2026-10-16", platform="Amazon", market="US", currency="USD")
        self.assertEqual(data["meta"]["sheet"], "产品导出")
        self.assertEqual(data["records"][0]["sales_growth"], 12)
        self.assertEqual(data["records"][0]["age_days"], 15)

    def test_xlsx_formula_without_cached_value_stays_missing(self):
        excel = tabular.excel_module()
        book = excel.Workbook()
        book.active.append(["ASIN", "月销量", "评分"])
        book.active.append(["XLSX-2", "=1000+200", 3.2])
        path = self.path / "formula.xlsx"
        book.save(path)
        book.close()
        data = selection.read_csv(path, as_of="", platform="", market="", currency="", partial=True)
        self.assertIsNone(data["records"][0]["monthly_sales"])

    def test_batch_save_dedup_and_restore_date_unknown(self):
        store = core.Store(self.path / "store")
        try:
            first = selection.prepare_text("衬衫\n休闲裤")
            selection.persist(store, first)
            selection.persist(store, selection.prepare_text("衬衫"))
            self.assertEqual(len(store.list("candidate")), 2)
            backup = self.path / "backup.json"
            store.backup(backup)
            store.restore(backup)
            self.assertEqual(len(store.list("candidate")), 2)
            self.assertTrue(all(x["as_of"] == "" for x in store.list("candidate")))
        finally:
            store.close()
