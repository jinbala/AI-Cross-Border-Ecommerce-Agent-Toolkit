"""Acceptance test of the independently packaged program, not the source interpreter."""
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
import tempfile
from desktop_app.build import EXECUTABLE_NAME


def main():
    root = Path(__file__).resolve().parents[2]
    build = root / "desktop_app/.build/tests"
    build.mkdir(parents=True, exist_ok=True)
    executable = root / "桌面版" / EXECUTABLE_NAME
    assert executable.is_file(), "请先打包桌面程序。"
    with tempfile.TemporaryDirectory(dir=build) as directory:
        data = Path(directory) / "business-data"
        result = subprocess.run([str(executable), "--smoke-test", "--data-dir", str(data)],
                                cwd=directory, timeout=40)
        if result.returncode:
            log = data / "startup_error.log"
            raise AssertionError(log.read_text(encoding="utf-8") if log.exists() else result.returncode)
        with closing(sqlite3.connect(data / "workbench.db")) as connection:
            row = connection.execute("SELECT value FROM settings WHERE key='smoke_test'").fetchone()
            assert row == ('"passed"',), row
    print("Release passed: standalone executable, all screens, 7 workflow resources, market scripts, pricing and encrypted credentials.")


if __name__ == "__main__":
    main()
