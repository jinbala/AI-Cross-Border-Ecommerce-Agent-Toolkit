param([string]$PackageDirectory, [switch]$Open)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PackageDirectory) { $PackageDirectory = Join-Path $projectRoot 'dist\desktop' }
$PackageDirectory = (Resolve-Path -LiteralPath $PackageDirectory).Path
$appDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'PantsSelectionWorkbench\App'
$marker = Join-Path $appDirectory 'installation.json'
if ((Test-Path -LiteralPath $appDirectory) -and (Get-ChildItem -LiteralPath $appDirectory -Force | Select-Object -First 1)) {
    if (-not (Test-Path -LiteralPath $marker)) { throw '目标安装目录已有其他文件；未进行覆盖。' }
    $previous = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($previous.app_id -ne 'pants-selection-workbench-v1') { throw '目标安装目录不属于本应用；未进行覆盖。' }
}
if (-not (Test-Path -LiteralPath (Join-Path $PackageDirectory 'PantsWorkbench.exe'))) { throw '未找到桌面程序，请先构建。' }
New-Item -ItemType Directory -Path $appDirectory -Force | Out-Null
Copy-Item -Path (Join-Path $PackageDirectory '*') -Destination $appDirectory -Recurse -Force
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $appDirectory 'source-path.txt'), (Join-Path $projectRoot 'results\pants-tool.html'), $utf8)
$info = [PSCustomObject]@{ app_id = 'pants-selection-workbench-v1'; installed_at = (Get-Date).ToString('o'); workspace = $projectRoot }
[System.IO.File]::WriteAllText($marker, ($info | ConvertTo-Json), $utf8)
$exe = Join-Path $appDirectory 'PantsWorkbench.exe'
$shell = New-Object -ComObject WScript.Shell
function Add-WorkbenchShortcut([string]$directory) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $shortcutPath = Join-Path $directory '裤装选品工作台.lnk'
    if (Test-Path -LiteralPath $shortcutPath) {
        $oldShortcut = $shell.CreateShortcut($shortcutPath)
        if ($oldShortcut.TargetPath -ne $exe) { $shortcutPath = Join-Path $directory ('裤装选品工作台-' + (Get-Date -Format 'yyyyMMddHHmmss') + '.lnk') }
    }
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $appDirectory
    $shortcut.IconLocation = (Join-Path $appDirectory 'pants.ico')
    $shortcut.Description = '男女裤装选品、搜索、收藏与导出'
    $shortcut.Save()
    Write-Host "已创建快捷方式：$shortcutPath"
}
Add-WorkbenchShortcut ([Environment]::GetFolderPath('Desktop'))
Add-WorkbenchShortcut ([Environment]::GetFolderPath('Programs'))
Write-Host "安装完成：$exe"
if ($Open) { Start-Process -FilePath $exe -WorkingDirectory $appDirectory }
