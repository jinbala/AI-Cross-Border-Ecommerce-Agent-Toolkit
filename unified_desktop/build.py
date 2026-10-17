"""Build one desktop application from the pants host and existing Python core."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "integrations/pants"
BUILD = ROOT / "desktop_app/.build/unified"
DEPS = ROOT / "desktop_app/.build/deps"
OUTPUT = ROOT / "桌面版/服装生意工作台-2.0"
EXE = OUTPUT / "服装生意工作台.exe"


def run(args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def main():
    global OUTPUT, EXE
    parser = argparse.ArgumentParser()
    parser.add_argument("--webview-sdk", type=Path)
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--archive", type=Path, default=ROOT / "服装生意工作台-整合版-2.0.zip")
    args = parser.parse_args()
    OUTPUT = args.output_dir.resolve()
    EXE = OUTPUT / "服装生意工作台.exe"
    if sys.platform != "win32":
        raise SystemExit("Windows 桌面包需要在 Windows 构建。")
    sdk_candidates = [args.webview_sdk, BUILD / "webview2/1.0.2903.40",
                      ROOT.parent / "product-selection-specialist-skill-1/results/.desktop-sdk/1.0.2903.40"]
    sdk = next((p for p in sdk_candidates if p and (p / "lib/net462/Microsoft.Web.WebView2.Core.dll").is_file()), None)
    if sdk is None:
        raise SystemExit("请先获取 Microsoft.Web.WebView2 1.0.2903.40 SDK，并用 --webview-sdk 指向解压目录。")
    BUILD.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(DEPS), PYINSTALLER_CONFIG_DIR=str(BUILD / "pyinstaller-cache"))
    if not args.skip_backend:
        command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
                   "--name", "GarmentBackend", "--contents-directory", "runtime", "--paths", ROOT,
                   "--distpath", BUILD / "dist", "--workpath", BUILD / "work", "--specpath", BUILD,
                   "--hidden-import", "statistics", "--hidden-import", "openpyxl"]
        for folder in ("Agents", "Templates", "docs"):
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and path.suffix.lower() in (".md", ".py", ".yaml", ".json", ".csv"):
                    command += ["--add-data", f"{path}:{path.parent.relative_to(ROOT)}"]
        command.append(ROOT / "desktop_app/service.py")
        run(command, cwd=ROOT, env=env)
    shutil.copytree(BUILD / "dist/GarmentBackend", OUTPUT / "backend", dirs_exist_ok=True)
    html_dir = BUILD / "html"
    # A release never embeds the developer's real merchant cache.
    run(["node", VENDOR / "scripts/build_local_tool.mjs", "--data", BUILD / "no-bundled-merchant-data.json", "--output-dir", html_dir], cwd=VENDOR)
    html = (html_dir / "pants-tool.html").read_text(encoding="utf-8")
    html = html.replace("<title>裤装选品工作台</title>", "<title>服装生意工作台 2.0</title>")
    html = html.replace("<h1>裤装选品工作台</h1>", "<h1>选品找款</h1>")
    for original, replacement in (("全部裤装", "全部服装"), ("全部裤型", "全部款型"), ("筛选裤装", "筛选服装"), ("查看全部裤装", "查看全部服装"), (">裤型<", ">款型<")):
        html = html.replace(original, replacement)
    for control in ("fast-ranking", "collection-options", "update-summary", "update-plan", "category-choices", "factory-sales"):
        if f'id="{control}"' not in html:
            raise SystemExit(f"选品页面缺少控件：{control}")
    business_markup = (ROOT / "unified_desktop/business.html").read_text(encoding="utf-8")
    interface_css = (ROOT / "unified_desktop/interface.css").read_text(encoding="utf-8")
    html = html.replace("</main><script>", business_markup + "<style>" + interface_css + "</style></main><script>")
    addon = (ROOT / "unified_desktop/business.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    html = html.replace("</script></body>", "\n" + addon + "\n</script></body>")
    assets = OUTPUT / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "pants-tool.html").write_text(html, encoding="utf-8")
    for name, output in (("capture_compass_product.mjs", "compass-capture.js"), ("compass_navigation.mjs", "compass-navigation.js")):
        code = (VENDOR / "scripts" / name).read_text(encoding="utf-8")
        code = code[code.index("export function"):].replace("export function", "function")
        (assets / output).write_text(code, encoding="utf-8")
    shutil.copy2(VENDOR / "references/category-catalog.yaml", assets / "compass-categories.json")
    for name in ("Microsoft.Web.WebView2.Core.dll", "Microsoft.Web.WebView2.WinForms.dll"):
        shutil.copy2(sdk / "lib/net462" / name, OUTPUT / name)
    shutil.copy2(sdk / "runtimes/win-x64/native/WebView2Loader.dll", OUTPUT / "WebView2Loader.dll")
    shutil.copy2(ROOT / "desktop_app/assets/app.ico", OUTPUT / "pants.ico")
    shutil.copy2(VENDOR / "desktop/app.config", OUTPUT / (EXE.name + ".config"))
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    compile_command = [compiler, "/nologo", "/target:winexe", "/platform:x64", "/codepage:65001", "/optimize+", f"/out:{EXE}",
                       f"/win32icon:{OUTPUT / 'pants.ico'}", f"/win32manifest:{VENDOR / 'desktop/app.manifest'}"]
    compile_command += [f"/reference:{name}" for name in ("System.dll", "System.Core.dll", "System.Drawing.dll", "System.Windows.Forms.dll", "System.Web.dll", "System.Web.Extensions.dll")]
    compile_command += [f"/reference:{OUTPUT / name}" for name in ("Microsoft.Web.WebView2.Core.dll", "Microsoft.Web.WebView2.WinForms.dll")]
    compile_command += [f"/resource:{VENDOR / 'tests/fixtures' / name},{resource}" for name, resource in (("compass-desktop.html", "CompassFixture"), ("compass-update.html", "CompassUpdateFixture"))]
    compile_command += [VENDOR / "desktop" / name for name in ("PantsWorkbench.cs", "CompassPanel.cs", "CompassUpdater.cs", "WorkbenchNavigation.cs")]
    compile_command.append(ROOT / "unified_desktop/BusinessBridge.cs")
    run(compile_command, cwd=ROOT)
    shutil.copy2(ROOT / "LICENSE", OUTPUT / "LICENSE.txt")
    notices = [(VENDOR / "LICENSE").read_text(encoding="utf-8")]
    for package in ("openpyxl", "et_xmlfile"):
        notices += [f"{package}\n{p.read_text(encoding='utf-8')}" for p in DEPS.glob(package + "-*.dist-info/LICEN*") if p.is_file()]
    for path in sdk.iterdir():
        if path.is_file() and path.name.lower().startswith(("license", "notice")):
            notices.append(path.read_text(encoding="utf-8-sig"))
    (OUTPUT / "THIRD_PARTY_LICENSES.txt").write_text("\n\n".join(notices), encoding="utf-8")
    shutil.copy2(ROOT / "unified_desktop/使用说明.txt", OUTPUT / "使用说明.txt")
    archive = args.archive.resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        files = [EXE, OUTPUT / (EXE.name + '.config'), OUTPUT / 'pants.ico', OUTPUT / 'LICENSE.txt',
                 OUTPUT / 'THIRD_PARTY_LICENSES.txt', OUTPUT / '使用说明.txt']
        files += list(OUTPUT.glob('*.dll'))
        files += [p for folder in ('assets', 'backend') for p in (OUTPUT / folder).rglob('*') if p.is_file()]
        for path in sorted(files):
            relative = path.relative_to(OUTPUT)
            if not any(p.lower() in ("data", "userdata", "__pycache__") for p in relative.parts):
                target.write(path, Path("服装生意工作台-2.0") / relative)
    print(f"READY: {EXE}\nZIP: {archive}")


if __name__ == "__main__":
    main()
