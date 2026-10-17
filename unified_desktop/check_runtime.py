"""Check native activation and packaged worker reuse using disposable data only."""
import argparse
import ctypes
import json
import shutil
import statistics
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = '服装生意工作台.exe'


def until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise AssertionError('等待程序状态超时')


def instances(app, folder):
    processes = []
    user32 = ctypes.windll.user32
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    command = [str(app/NAME), '--instance-test-host', str(folder)]
    primary = subprocess.Popen(command)
    processes.append(primary)
    try:
        until(lambda: (folder/'ready').is_file())
        pid, handle = map(int, (folder/'ready').read_text().split(':'))
        assert pid == primary.pid
        user32.ShowWindow(handle, 6)  # Minimize the isolated native test window.
        until(lambda: user32.IsIconic(handle))
        # A copy in a different directory must also find the existing instance.
        copy = folder/'another-install'
        copy.mkdir()
        for file in app.iterdir():
            if file.is_file() and file.suffix in ('.exe', '.dll', '.config'):
                shutil.copy2(file, copy/file.name)
        secondary = subprocess.Popen([str(copy/NAME), *command[1:]], cwd=copy)
        processes.append(secondary)
        assert secondary.wait(timeout=10) == 0
        until(lambda: (folder/'activation.log').exists() and not user32.IsIconic(handle))
        launches = [subprocess.Popen(command + (['--open-compass'] if i == 0 else [])) for i in range(8)]
        processes.extend(launches)
        assert all(p.wait(timeout=10) == 0 for p in launches)
        until(lambda: 'compass:Normal' in (folder/'activation.log').read_text())
        assert primary.poll() is None
        user32.PostMessageW(handle, 0x10, 0, 0)
        assert primary.wait(timeout=10) == 0
        (folder/'ready').unlink()
        restarted = subprocess.Popen(command)
        processes.append(restarted)
        until(lambda: (folder/'ready').is_file())
        assert int((folder/'ready').read_text().split(':')[0]) == restarted.pid
        # Simulate an application crash, then verify the lock is recoverable.
        restarted.kill()
        restarted.wait(timeout=10)
        (folder/'ready').unlink()
        recovered = subprocess.Popen(command)
        processes.append(recovered)
        until(lambda: (folder/'ready').is_file())
        handle = int((folder/'ready').read_text().split(':')[1])
        user32.PostMessageW(handle, 0x10, 0, 0)
        assert recovered.wait(timeout=10) == 0
        return dict(singleInstance=True, restoredFromMinimized=True, crossDirectory=True,
                    compassActivation=True, rapidLaunches=8, cleanRestart=True, crashRecovery=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)


def timings(app, folder, baseline=None):
    helper = app/'backend/GarmentBackend.exe'
    request = b'{"command":"state"}'
    cold = []
    for _ in range(5):
        started = time.perf_counter()
        result = subprocess.run([str((baseline or app)/'backend/GarmentBackend.exe'), '--data-dir', str(folder)],
                                input=request, capture_output=True, timeout=30)
        assert result.returncode == 0 and json.loads(result.stdout)['ok']
        cold.append((time.perf_counter()-started)*1000)
    worker = subprocess.Popen([str(helper), '--serve', '--data-dir', str(folder)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        warm = []
        for i in range(21):
            started = time.perf_counter()
            worker.stdin.write(request+b'\n')
            worker.stdin.flush()
            assert json.loads(worker.stdout.readline())['ok']
            if i:
                warm.append((time.perf_counter()-started)*1000)
        assert worker.poll() is None
        worker.stdin.close()
        assert worker.wait(timeout=10) == 0
        assert not worker.stderr.read()
        return dict(oneShotMedianMs=round(statistics.median(cold), 2),
                    warmWorkerMedianMs=round(statistics.median(warm), 2), warmRequests=len(warm))
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.wait(timeout=10)
        worker.stdout.close()
        worker.stderr.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-dir', type=Path, default=ROOT/'桌面版/服装生意工作台-2.0')
    parser.add_argument('--baseline-dir', type=Path)
    args = parser.parse_args()
    folder = ROOT/'desktop_app/.build/unified/tests'/('runtime-'+uuid.uuid4().hex[:12])
    folder.mkdir(parents=True)
    result = dict(instances=instances(args.app_dir.resolve(), folder),
                  backend=timings(args.app_dir.resolve(), folder/'benchmark-data', args.baseline_dir))
    (folder/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    print(folder/'result.json')


if __name__ == '__main__':
    main()
