import assert from 'node:assert/strict';
import test from 'node:test';
import { WorkbenchStateCache } from '../state_cache.mjs';

const deferred = () => {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};

test('page switches share one pending read, reuse fresh data and expire', async () => {
  let reads=0,now=0;
  const cache=new WorkbenchStateCache(async()=>({revision:++reads}),{ttl:100,clock:()=>now});
  const [a,b]=await Promise.all([cache.get(),cache.get()]);
  assert.equal(a,b);assert.equal(reads,1);
  assert.equal(await cache.get(),a);
  now=101;assert.equal((await cache.get()).revision,2);
  assert.equal((await cache.get(true)).revision,3);
});

test('a write invalidates reads already in flight and prevents stale replacement', async () => {
  const old=deferred(),fresh=deferred();let reads=0;
  const cache=new WorkbenchStateCache(()=>++reads===1?old.promise:fresh.promise);
  const first=cache.get();cache.invalidate();const second=cache.get();
  fresh.resolve({value:'after save'});assert.equal((await second).value,'after save');
  old.resolve({value:'before save'});assert.equal((await first).value,'after save');
  assert.equal((await cache.get()).value,'after save');assert.equal(reads,2);
});

test('failed reads can be retried and invalidation reloads saved state', async () => {
  let reads=0;
  const cache=new WorkbenchStateCache(async()=>{if(++reads===1)throw new Error('offline');return {revision:reads};});
  await assert.rejects(cache.get(),/offline/);
  assert.equal((await cache.get()).revision,2);
  cache.invalidate();assert.equal((await cache.get()).revision,3);
});
