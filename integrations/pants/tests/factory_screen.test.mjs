import test from 'node:test';
import assert from 'node:assert/strict';
import {observedRange, factoryScreen} from '../scripts/factory_screen.mjs';

test('observed intervals preserve bounds and ambiguous values stay unknown',()=>{
  assert.deepEqual(observedRange('1万–2.5万'),{lower:10000,upper:25000});
  assert.deepEqual(observedRange('1–2万'),{lower:10000,upper:20000});
  assert.deepEqual(observedRange('3%–8%',true),{lower:3,upper:8});
  for(const raw of ['待验证','1万以上','<100','1000-100','1万-2','abc',null]) assert.equal(observedRange(raw),null);
  assert.equal(observedRange('0.03',true),null);
  assert.equal(observedRange('120%',true),null);
});

test('factory matches use conservative lower bounds, original period and manual keywords',()=>{
  const group={product:{name:'大码直筒牛仔裤',apparel:{type:'牛仔裤'}},primary_observation:{metrics:{sales_count:'100-500',click_conversion_rate:'2%-8%'}}};
  const prefs={minSales:100,minConversion:3,keywords:'牛仔 卫衣'};
  assert.equal(factoryScreen(group,prefs).qualifies,false);
  assert.match(factoryScreen(group,prefs).reasons.join('；'),/转化下限 2%/);
  prefs.minConversion=2;
  assert.equal(factoryScreen(group,prefs).qualifies,true);
  assert.match(factoryScreen(group,prefs).reasons.join('；'),/匹配擅长款：牛仔/);
  prefs.minSales=101;
  assert.equal(factoryScreen(group,prefs).qualifies,false);
  assert.equal(group.primary_observation.metrics.sales_count,'100-500');
  delete group.primary_observation.metrics.sales_count;
  assert.equal(factoryScreen(group,prefs).missing,true);
  assert.equal(factoryScreen(group,prefs).qualifies,false);
  assert.throws(()=>factoryScreen(group,{minSales:0,minConversion:101}),/0—100/);
});
