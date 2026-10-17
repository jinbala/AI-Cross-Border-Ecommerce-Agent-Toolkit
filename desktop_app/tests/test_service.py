import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from desktop_app import core, service


class UnifiedServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = core.Store(Path(self.temp.name) / 'data')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def payload(self, stamp='2026-10-12', price='¥99–¥150'):
        product = dict(id='12345678901234567890', name='测试女款直筒牛仔裤', shop='测试店铺', link='https://example.com/product?id=123&token=private',
                       price_min=None, price_band_display=price, apparel=dict(gender='女款', type='牛仔裤', fabric='', sizes=''))
        observation = dict(product=product, ranking_date=stamp, rank=1, category_path=['服饰内衣','服装','女装','牛仔裤'],
                           source_filters=dict(price_band_label='99–150 元'), metrics=dict(payment_amount='¥1万–¥2万', sales_count='100–250'))
        return dict(meta=dict(source_type='product_ranking', ranking_date=stamp, observed_identity='测试店铺', period='近7天 · '+stamp, is_demo=False),
                    group=dict(product=product, observations=[observation]))

    def call(self, action, **kwargs):
        return service.dispatch(self.store, action, kwargs)

    def test_intervals_never_become_factory_prices_or_exact_monthly_sales(self):
        result=self.call('import_compass', **self.payload())
        item=result['candidate']
        self.assertNotIn('monthly_sales', item['evidence'])
        self.assertEqual(item['status'], '资料待补')
        self.assertEqual(item['evidence']['observations'][0]['metrics']['成交件数（来源区间）'], '100–250')
        self.assertNotIn('token', item['evidence']['source_url'])
        product=self.call('create_product', candidate_id=result['candidate_id'])
        self.assertEqual((product['cost'],product['supply_price'],product['retail_price']),('','',''))
        self.assertIn('近7天',product['notes'])
        self.assertIn('99–150',product['notes'])

    def test_source_updates_preserve_factory_data_and_distinct_periods(self):
        first=self.call('import_compass',**self.payload())
        product=self.call('create_product',candidate_id=first['candidate_id'])
        product.update(cost='20',supply_price='30',fabric='本厂确认面料')
        self.call('save_product',product=product)
        self.call('import_compass',**self.payload())
        second=self.call('import_compass',**self.payload('2026-10-17','¥150–¥200'))
        self.assertEqual(first['candidate_id'],second['candidate_id'])
        self.assertEqual(len(second['candidate']['evidence']['observations']),2)
        again=self.call('create_product',candidate_id=first['candidate_id'])
        self.assertEqual((again['cost'],again['supply_price'],again['fabric']),('20','30','本厂确认面料'))
        self.assertEqual(len(self.store.list('product')),1)

    def test_invalid_identity_id_and_date_rejected_before_saving(self):
        variants=[]
        a=self.payload();a['meta']['observed_identity']='';variants.append(a)
        a=self.payload();a['group']['product']['id']=12345678901234567890;variants.append(a)
        a=self.payload();a['group']['observations'][0]['ranking_date']='2026-10-01';variants.append(a)
        a=self.payload();a['group']['observations'][0]['rank']=True;variants.append(a)
        a=self.payload();a['group']['product']['link']='https://user:secret@example.com/p';variants.append(a)
        for payload in variants:
            with self.assertRaises(ValueError):self.call('import_compass',**payload)
        self.assertEqual(self.store.list('candidate'),[])

    def test_demo_and_real_candidates_do_not_overwrite_each_other(self):
        real=self.call('import_compass',**self.payload())
        payload=self.payload();payload['meta']['is_demo']=True
        demo=self.call('import_compass',**payload)
        self.assertNotEqual(real['candidate_id'],demo['candidate_id'])
        self.assertTrue(demo['candidate']['evidence']['is_demo'])
        product=self.call('create_product',candidate_id=demo['candidate_id'])
        self.assertTrue(product['is_demo'])
        self.assertIn('演示（虚构',product['notes'])
        product['name']='试用改名'
        self.assertTrue(self.call('save_product',product=product)['is_demo'])
        report=self.call('pricing',product_id=product['id'],values=dict(price=30,production=20,currency='CNY'),save=True)
        self.assertIn('演示款测算',report['report'])
        exp=self.call('save_experiment',experiment=dict(name='试用',product_id=product['id'],date='2026-10-17',status='计划中'))
        self.assertTrue(self.store.get(exp['id'])['is_demo'])
        prompt=self.call('compose',module=2,product_id=product['id'],platform='供货',market='中国')['prompt']
        self.assertIn('演示任务',prompt)

    def test_backup_roundtrip_keeps_observations_and_linked_product(self):
        first=self.call('import_compass',**self.payload())
        product=self.call('create_product',candidate_id=first['candidate_id'])
        path=Path(self.temp.name)/'backup.json'
        self.call('backup',path=str(path))
        self.call('restore',path=str(path))
        self.assertEqual(self.store.get(first['candidate_id'])['product_id'],product['id'])
        self.assertEqual(len(self.store.get(first['candidate_id'])['evidence']['observations']),1)

    def test_full_intake_pricing_workflow_and_experiment_handoff(self):
        result=self.call('intake',text='亚麻衬衫\n休闲裤')
        product=self.call('create_product',candidate_id=result['ids'][0])
        product.update(cost='20',supply_price='30')
        self.call('save_product',product=product)
        pricing=self.call('pricing',values=dict(price=30,production=20,quantity=2,currency='CNY'),save=True)
        self.assertEqual(pricing['result']['batch_profit'],20)
        task=self.call('compose',module=2,product_id=product['id'],platform='供货 / 批发',market='中国',brief='确认面料')
        self.assertIn(product['name'],task['prompt'])
        self.assertIn('确认面料',task['prompt'])
        self.call('save_experiment',experiment=dict(name=product['name'],channel='供货',date='2026-10-17',status='计划中',budget=100,spent=0,revenue=0,hours=0))
        self.assertEqual(len(self.call('state')['experiments']),1)

    def test_cross_record_type_edit_is_rejected(self):
        artifact=self.store.save('artifact',dict(name='测试',kind='报告',content='正文'))
        with self.assertRaises(ValueError):self.call('save_product',product=dict(id=artifact,name='误改'))
        self.assertEqual(self.store.get(artifact)['content'],'正文')

    def test_ai_settings_are_redacted_and_requests_use_saved_key(self):
        with patch('desktop_app.core.protect_key',return_value='encrypted'),patch('desktop_app.core.unprotect_key',return_value='secret'):
            value=self.call('save_settings',api_base='https://example.com/v1',api_model='test',api_key='secret',monthly_budget=3000)
            self.assertTrue(value['has_key'])
            self.assertNotIn('secret',json.dumps(self.call('state')))
            with patch('desktop_app.core.call_ai',return_value='模拟文字结果') as mock:
                value=self.call('generate_ai',module=0,platform='供货',market='中国',brief='测试')
                self.assertEqual(value['content'],'模拟文字结果')
                self.assertEqual(mock.call_args.args[1],'secret')
        self.assertEqual(len(self.store.list('artifact')),1)

    def test_condition_filter_uses_same_existing_rules(self):
        result=self.call('intake',text='标题\t月销量\t评分\n测试衬衫\t1200\t3.2',strategy='factory_upgrade',platform='Amazon',market='US',currency='USD',as_of='2026-10-17')
        self.assertEqual(result['counts']['符合筛选'],1)

    def test_only_explicitly_saved_cny_quotes_update_factory_fields(self):
        source=self.call('import_compass',**self.payload())
        product=self.call('create_product',candidate_id=source['candidate_id'])
        self.call('pricing',values=dict(price='30',production='20',currency='CNY'),product_id=product['id'],save=False)
        self.assertEqual(self.store.get(product['id'])['cost'],'')
        self.call('pricing',values=dict(price='30',production='20',currency='CNY'),product_id=product['id'],save=True)
        self.call('pricing',values=dict(price='10',production='4',currency='USD'),product_id=product['id'],save=True)
        product=self.store.get(product['id'])
        self.assertEqual((product['cost'],product['supply_price']),('20','30'))

    def test_invalid_settings_do_not_partially_replace_existing_values(self):
        self.store.set_setting('api_model','existing')
        with self.assertRaises(ValueError):
            self.call('save_settings',api_base='https://example.com/v1',api_model='new',monthly_budget=-1)
        self.assertEqual(self.store.setting('api_model'),'existing')

    def test_json_stdin_protocol_from_independent_working_directory(self):
        root=Path(__file__).resolve().parents[2]
        response=subprocess.run([sys.executable,str(root/'desktop_app/service.py'),'--data-dir',str(Path(self.temp.name)/'isolated')],
                                input=json.dumps(dict(command='intake',args=dict(text='宽松衬衫')),ensure_ascii=False).encode('utf-8'),capture_output=True,cwd=self.temp.name,timeout=20)
        data=json.loads(response.stdout)
        self.assertTrue(data['ok'],data)
        self.assertEqual(len(data['data']['ids']),1)


if __name__=='__main__':unittest.main()
