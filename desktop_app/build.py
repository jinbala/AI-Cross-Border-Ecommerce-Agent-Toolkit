"""Build the portable Windows executable without changing global Python packages."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "desktop_app" / ".build"
DEPS = BUILD / "deps"
OUTPUT = ROOT / "桌面版"
EXECUTABLE_NAME = "服装生意工作台-1.3.exe"
RUNTIME_NAME = "runtime-1.3"


def package_release():
    archive = ROOT / "服装生意工作台-Windows.zip"
    files = [OUTPUT / EXECUTABLE_NAME, OUTPUT / "使用说明.txt", OUTPUT / "LICENSE.txt"]
    if (OUTPUT / "THIRD_PARTY_LICENSES.txt").is_file():
        files.append(OUTPUT / "THIRD_PARTY_LICENSES.txt")
    files += [p for p in (OUTPUT / RUNTIME_NAME).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(files):
            package.write(path, Path("服装生意工作台") / path.relative_to(OUTPUT))
    return archive


def main():
    if sys.platform != "win32":
        raise SystemExit("Please build the Windows executable on Windows.")
    if not (DEPS / "PyInstaller").is_dir():
        raise SystemExit("Run: python -m pip install --target desktop_app/.build/deps -r desktop_app/requirements-build.txt")
    OUTPUT.mkdir(exist_ok=True)
    # A workspace-local Tcl copy also works inside restricted development environments.
    tcl_root = Path(sys.base_prefix) / "tcl"
    local_tcl = BUILD / "tcl-runtime"
    for name in ("tcl8.6", "tk8.6"):
        shutil.copytree(tcl_root / name, local_tcl / name, dirs_exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(DEPS), TCL_LIBRARY=str(local_tcl / "tcl8.6"), TK_LIBRARY=str(local_tcl / "tk8.6"),
               PYINSTALLER_CONFIG_DIR=str(BUILD / "pyinstaller-cache"))
    arguments = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--contents-directory", RUNTIME_NAME,
                 "--name", "GarmentWorkbench", "--distpath", str(BUILD / "dist"),
                 "--workpath", str(BUILD / "work"), "--specpath", str(BUILD),
                 "--icon", str(ROOT / "desktop_app/assets/app.ico"),
                 "--paths", str(ROOT), "--hidden-import", "desktop_app.core", "--hidden-import", "statistics", "--hidden-import", "openpyxl"]
    for folder in ("Agents", "Templates", "docs"):
        # Include the tested workflows, not the unedited source PDF.
        for file in (ROOT / folder).rglob("*"):
            if file.is_file() and file.suffix.lower() in (".md", ".py", ".yaml", ".json", ".csv"):
                arguments.extend(["--add-data", f"{file}:{file.parent.relative_to(ROOT)}"])
    arguments.extend(["--add-data", f"{ROOT / 'desktop_app/assets/app.ico'}:desktop_app/assets",
                      str(ROOT / "desktop_app/app.py")])
    subprocess.run(arguments, cwd=ROOT, env=env, check=True)
    executable = OUTPUT / EXECUTABLE_NAME
    bundle = BUILD / "dist/GarmentWorkbench"
    shutil.copytree(bundle / RUNTIME_NAME, OUTPUT / RUNTIME_NAME, dirs_exist_ok=True)
    shutil.copy2(bundle / "GarmentWorkbench.exe", executable)
    shutil.copy2(ROOT / "desktop_app/使用说明.txt", OUTPUT / "使用说明.txt")
    shutil.copy2(ROOT / "LICENSE", OUTPUT / "LICENSE.txt")
    notices = []
    for package in ("openpyxl", "et_xmlfile"):
        for path in sorted(DEPS.glob(package + "-*.dist-info/LICEN*")):
            if path.is_file():
                notices.append(f"{package} · {path.name}\n\n{path.read_text(encoding='utf-8')}\n")
    (OUTPUT / "THIRD_PARTY_LICENSES.txt").write_text("\n".join(notices), encoding="utf-8")
    size = sum(p.stat().st_size for p in OUTPUT.rglob("*") if p.is_file() and "data" not in p.relative_to(OUTPUT).parts)
    print(f"\nREADY: {executable}\nPortable folder size: {size / 1024 / 1024:.1f} MB")
    print(f"ZIP: {package_release()}")


if __name__ == "__main__":
    main()
