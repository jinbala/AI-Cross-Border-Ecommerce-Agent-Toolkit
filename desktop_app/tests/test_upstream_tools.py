import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from desktop_app import core, service, upstream_tools as tools


class UpstreamDesktopTests(unittest.TestCase):
    def test_original_video_sample_preserves_word_timing(self):
        path = core.ROOT / 'Agents/05_Product_Video_Agent/examples/narration_airfryer.txt'
        result = tools.video_report(dict(script=path.read_text(encoding='utf-8'), target=30))
        self.assertEqual(result['language'], 'words')
        self.assertEqual(result['total_seconds'], 26)
        self.assertTrue(result['target_pass'])
        self.assertEqual(len(result['rows']), 7)

    def test_chinese_counting_uses_characters_and_original_subtitle_length(self):
        result = tools.video_report(dict(script='高腰直筒牛仔裤\n面料舒适', rate=4, target=3, subtitle_max=5))
        self.assertEqual(result['total_seconds'], 2.75)
        self.assertEqual(result['rows'][0]['words'], 7)
        self.assertEqual(result['rows'][0]['subtitle_chars'], 7)
        self.assertEqual(result['rows'][0]['text'], '高腰直筒牛仔裤')
        self.assertTrue(result['issues'])
        self.assertIn('不是实际音频测量', result['report'])

    def test_invalid_video_parameters_do_not_silently_produce_a_result(self):
        for args in [dict(script=''),dict(script='# 注释'),dict(script='a',rate=0),dict(script='a',rate='NaN'),
                     dict(script='a',target=-1),dict(script='a',subtitle_max=1.5),dict(script='a',language='unknown')]:
            with self.subTest(args=args), self.assertRaises(ValueError):tools.video_report(args)

    def test_original_review_sample_matches_upstream_counts_and_points(self):
        base = core.ROOT / 'Agents/07_Review_Analysis_Agent/examples'
        result = tools.review_report(dict(reviews_text=(base/'sample-reviews.csv').read_text(encoding='utf-8-sig'),
                                          points_text=(base/'sample-selling-points.csv').read_text(encoding='utf-8-sig')))
        self.assertEqual(result['valid_count'], 128)
        self.assertEqual((result['reviews']['good'],result['reviews']['mid'],result['reviews']['bad']), (104,11,13))
        self.assertEqual(result['reviews']['attribution_mismatch'], 0)
        self.assertEqual(len(result['points']['rows']), 7)

    def test_all_good_or_all_invalid_reviews_handle_zero_denominators(self):
        result = tools.review_report(dict(reviews_text='rating\n5\n4'))
        self.assertEqual(result['reviews']['bad'], 0)
        self.assertIn('没有差评',result['report'])
        result = tools.review_report(dict(reviews_text='rating\nNaN\ninf\n2.5\n0\n6\n-1'))
        self.assertEqual(result['valid_count'], 0)
        self.assertEqual(result['reviews']['bad'], 0)
        self.assertEqual(result['reviews']['unrated'], 6)
        json.dumps(result, allow_nan=False)

    def test_missing_attribution_and_dirty_ratings_remain_visible(self):
        result = tools.review_report(dict(reviews_text='评分\t归因\n5\t\n1\t误解型\n2\t\nNaN\t\n2.5\t'))
        self.assertEqual(result['valid_count'], 3)
        self.assertEqual(result['reviews']['unrated'], 2)
        self.assertEqual(len(result['reviews']['unattributed']), 1)
        self.assertTrue(any('合计不完整' in x for x in result['warnings']))

    def test_csv_contract_and_invalid_selling_points_fail_clearly(self):
        for raw in ['评论\n好看', 'rating,rating\n5,4', 'rating\n5,extra']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):tools.review_report(dict(reviews_text=raw))
        for count in ['-1','1.5','NaN','1-3','']:
            with self.subTest(count=count), self.assertRaises(ValueError):
                tools.review_report(dict(reviews_text='rating\n5',points_text='卖点,频次,强度\n舒适,'+count+',强'))

    def test_import_preserves_file_bytes_and_supports_gb18030(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'reviews.csv';data='评分,归因\n1,误解型\n'.encode('gb18030');path.write_bytes(data)
            imported=tools.read_file(path,'reviews')
            result=tools.review_report(dict(reviews_text=imported['text']))
            self.assertEqual(result['reviews']['bad'],1)
            self.assertEqual(path.read_bytes(),data)
            path=Path(folder)/'oversized.txt';path.write_bytes(b'a'*(tools.LIMIT+1))
            with self.assertRaises(ValueError):tools.read_file(path,'video')
            with self.assertRaises(ValueError):tools.read_file(Path(folder)/'script.py','video')

    def test_service_examples_templates_and_report_storage_keep_demo_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            store=core.Store(Path(folder))
            try:
                example=service.dispatch(store,'tool_example',dict(tool='reviews'))
                result=service.dispatch(store,'review_report',example)
                self.assertTrue(result['is_demo'])
                self.assertIn('演示',result['report'])
                service.dispatch(store,'save_artifact',dict(name='【演示】评论报告',kind='分析报告',content=result['report']))
                self.assertEqual(len(store.list('artifact')),1)
                template=service.dispatch(store,'tool_template',dict(tool='reviews'))
                self.assertIn('评分',next(csv.reader(io.StringIO(template['content']))))
                self.assertTrue(template['filename'].endswith('.csv'))
            finally:store.close()

    def test_synced_skill_enters_market_workflow_as_reference(self):
        prompt=core.workflow_prompt(0,None,'供货 / 批发','中国','测试')
        self.assertIn('项目参考流程 · Skill 入口',prompt)
        self.assertIn('不得声称已经完成校验',prompt)


if __name__=='__main__':unittest.main()
