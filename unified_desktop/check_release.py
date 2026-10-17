"""Exercise the independently packaged host and helper using isolated fixtures."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import zipfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "桌面版/服装生意工作台-2.0/服装生意工作台.exe"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('unified', 'collector', 'update'), default='unified')
    parser.add_argument('--app-dir', type=Path, default=EXE.parent)
    parser.add_argument('--archive', type=Path, default=ROOT / '服装生意工作台-整合版-2.0.zip')
    args = parser.parse_args()
    folder = ROOT / 'desktop_app/.build/unified/tests'
    folder.mkdir(parents=True, exist_ok=True)
    # Keep the report and native-rendered screenshot available for inspection.
    run_dir = folder / (args.mode+'-'+uuid.uuid4().hex[:12])
    run_dir.mkdir()
    output = run_dir / 'result.json'
    flag = '--unified-smoke-test' if args.mode == 'unified' else '--'+args.mode+'-smoke-test'
    env = dict(os.environ)
    env.pop('GARMENT_WORKBENCH_DATA', None)
    try:
        result = subprocess.run([str(args.app_dir.resolve() / EXE.name), flag, str(output)], cwd=run_dir, env=env, timeout=240)
    except subprocess.TimeoutExpired:
        raise AssertionError(f'桌面测试超时；测试资料目录：{run_dir}') from None
    assert output.is_file(), f'没有生成测试结果，退出码 {result.returncode}；目录：{run_dir}'
    raw = output.read_text(encoding='utf-8-sig')
    assert not raw.startswith('ERROR'), raw
    data = json.loads(raw)
    assert result.returncode == 0, data
    if args.mode == 'unified':
        assert data['passed'] and data['unit_profit'] == 10 and data['rangeNotUsedAsPrice'], data
        assert data['upstreamTools']['video'] and data['upstreamTools']['reviews'] and data['upstreamTools']['staleResultCleared'] and data['upstreamTools']['marketSkill'] and data['upstreamTools']['demoReports'] == 2, data
        assert all(data['performance'][key] for key in ('workerReused', 'invalidRequestRecovered', 'concurrentRequestsQueued', 'workerRestartPreservedData')), data
        assert data['uiPerformance']['navigationReadsAvoided'] == 9 and data['uiPerformance']['artifactLoadedOnDemand'] and data['uiPerformance']['crossPageSearch'] and data['uiPerformance']['hiddenProductPreviewRemoved'], data
    else:
        assert data, '采集检查未返回结果。'
        if args.mode == 'collector':
            assert data['firstSaved'] and data['previousDataPreserved'] and data['invalidPageRejected'], data
        else:
            assert data['firstSaved'] and data['oldDataPreserved'] and data['customPriceVerified'], data
            assert data['fastRankingSaved'] and data['fastRankingState']['count'] == 8 and data['fastRankingState']['links'] == 0, data
            assert data['apparelSaved'] and data['discoveredCategories'] == 15 and data['factoryScreenState']['explained'], data
    print(f'{args.mode} release check: {output}')
    print(json.dumps(data, ensure_ascii=False)[:2500])
    archive = args.archive
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert not any('/data/' in name or '/UserData/' in name for name in names)
        for script in ('05_Product_Video_Agent/scripts/video_timing.py','07_Review_Analysis_Agent/scripts/review_stats.py','01_Market_Research_Agent/SKILL.md'):
            assert any(name.endswith('/Agents/'+script) for name in names), script
        assert package.testzip() is None


if __name__ == '__main__':
    main()
