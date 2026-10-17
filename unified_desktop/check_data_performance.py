"""Measure list payloads on synthetic reports, without reading merchant data."""
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from desktop_app import core, service


def main():
    with tempfile.TemporaryDirectory(prefix='workbench-list-') as folder:
        store = core.Store(folder)
        try:
            content = '人工构造的性能测试正文，非真实经营资料。\n' * 1000
            store.save_batch('artifact', [('report-'+str(i), dict(name='模拟报告'+str(i), kind='测试报告', content=content)) for i in range(200)])
            store.save_batch('candidate', [('candidate-'+str(i), dict(name='模拟款'+str(i), source_id=str(i), platform='测试', status='资料待补', review_status='待复核', evidence=dict(is_demo=True, observations=[content]))) for i in range(500)])
            result = {}
            for compact in (False, True):
                elapsed = []
                for _ in range(5):
                    start = time.perf_counter()
                    raw = json.dumps(service.dispatch(store, 'state', dict(compact=compact)), ensure_ascii=False).encode('utf-8')
                    elapsed.append((time.perf_counter()-start)*1000)
                result['compact' if compact else 'full'] = dict(bytes=len(raw), medianMs=round(statistics.median(elapsed), 2))
            result['payloadReductionPercent'] = round(100*(1-result['compact']['bytes']/result['full']['bytes']), 2)
            assert result['compact']['bytes'] < result['full']['bytes']/10
            assert service.dispatch(store, 'artifact_detail', dict(id='report-199'))['content'] == content
            print(json.dumps(result, ensure_ascii=False))
        finally:
            store.close()


if __name__ == '__main__':
    main()
