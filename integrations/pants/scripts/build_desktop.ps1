param([switch]$Install, [switch]$Open)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = Split-Path -Parent $PSScriptRoot
$sdkVersion = '1.0.2903.40'
$sdkDirectory = Join-Path $projectRoot "results\.desktop-sdk\$sdkVersion"
$packageDirectory = Join-Path $projectRoot 'dist\desktop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '需要 Windows .NET Framework 4.8（64 位）。' }
if (-not (Test-Path -LiteralPath (Join-Path $sdkDirectory 'lib\net462\Microsoft.Web.WebView2.Core.dll'))) {
    New-Item -ItemType Directory -Path $sdkDirectory -Force | Out-Null
    $base = "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/$sdkVersion/microsoft.web.webview2.$sdkVersion.nupkg"
    $archive = Join-Path $sdkDirectory 'webview2.zip'
    Write-Host '正在获取微软 WebView2 SDK（首次构建需要联网）…'
    Invoke-WebRequest -Uri $base -OutFile $archive -UseBasicParsing
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($archive, $sdkDirectory)
}
Push-Location $projectRoot
try {
    & node scripts/build_local_tool.mjs
    if ($LASTEXITCODE -ne 0) { throw '选品页面构建失败。' }
} finally { Pop-Location }
New-Item -ItemType Directory -Path (Join-Path $packageDirectory 'assets') -Force | Out-Null
foreach ($name in @('Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll')) {
    Copy-Item -LiteralPath (Join-Path $sdkDirectory "lib\net462\$name") -Destination $packageDirectory -Force
}
Copy-Item -LiteralPath (Join-Path $sdkDirectory 'runtimes\win-x64\native\WebView2Loader.dll') -Destination $packageDirectory -Force
Copy-Item -LiteralPath (Join-Path $projectRoot 'results\pants-tool.html') -Destination (Join-Path $packageDirectory 'assets\pants-tool.html') -Force
$captureCode = Get-Content -LiteralPath (Join-Path $projectRoot 'scripts\capture_compass_product.mjs') -Raw -Encoding UTF8
$captureCode = $captureCode.Substring($captureCode.IndexOf('export function')).Replace('export function', 'function')
[System.IO.File]::WriteAllText((Join-Path $packageDirectory 'assets\compass-capture.js'), $captureCode, (New-Object System.Text.UTF8Encoding $false))
$navigationCode = Get-Content -LiteralPath (Join-Path $projectRoot 'scripts\compass_navigation.mjs') -Raw -Encoding UTF8
$navigationCode = $navigationCode.Substring($navigationCode.IndexOf('export function')).Replace('export function', 'function')
[System.IO.File]::WriteAllText((Join-Path $packageDirectory 'assets\compass-navigation.js'), $navigationCode, (New-Object System.Text.UTF8Encoding $false))
Copy-Item -LiteralPath (Join-Path $projectRoot 'references\category-catalog.yaml') -Destination (Join-Path $packageDirectory 'assets\compass-categories.json') -Force
Copy-Item -LiteralPath (Join-Path $projectRoot 'desktop\app.config') -Destination (Join-Path $packageDirectory 'PantsWorkbench.exe.config') -Force
Copy-Item -LiteralPath (Join-Path $projectRoot 'desktop\README.md') -Destination (Join-Path $packageDirectory '使用说明.md') -Force
Get-ChildItem -LiteralPath $sdkDirectory -File | Where-Object { $_.Name -match '^(LICENSE|License|license|NOTICE)' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $packageDirectory -Force }
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap 256, 256
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::FromArgb(36, 86, 63))
$pantsBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(241, 235, 206))
$pantsPoints = [System.Drawing.Point[]]@((New-Object System.Drawing.Point 72, 48), (New-Object System.Drawing.Point 184, 48), (New-Object System.Drawing.Point 197, 208), (New-Object System.Drawing.Point 146, 208), (New-Object System.Drawing.Point 128, 120), (New-Object System.Drawing.Point 110, 208), (New-Object System.Drawing.Point 59, 208))
$graphics.FillPolygon($pantsBrush, $pantsPoints)
$waistPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(36, 86, 63)), 5
$graphics.DrawLine($waistPen, 73, 71, 183, 71)
$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$iconPath = Join-Path $packageDirectory 'pants.ico'
$stream = [System.IO.File]::Create($iconPath)
try { $icon.Save($stream) } finally { $stream.Dispose(); $icon.Dispose(); $waistPen.Dispose(); $pantsBrush.Dispose(); $graphics.Dispose(); $bitmap.Dispose() }
$exe = Join-Path $packageDirectory 'PantsWorkbench.exe'
& $compiler /nologo /target:winexe /platform:x64 /codepage:65001 /optimize+ "/out:$exe" "/win32icon:$iconPath" "/win32manifest:$(Join-Path $projectRoot 'desktop\app.manifest')" /reference:System.dll /reference:System.Core.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /reference:System.Web.dll /reference:System.Web.Extensions.dll "/reference:$(Join-Path $packageDirectory 'Microsoft.Web.WebView2.Core.dll')" "/reference:$(Join-Path $packageDirectory 'Microsoft.Web.WebView2.WinForms.dll')" "/resource:$(Join-Path $projectRoot 'tests\fixtures\compass-desktop.html'),CompassFixture" "/resource:$(Join-Path $projectRoot 'tests\fixtures\compass-update.html'),CompassUpdateFixture" (Join-Path $projectRoot 'desktop\PantsWorkbench.cs') (Join-Path $projectRoot 'desktop\CompassPanel.cs') (Join-Path $projectRoot 'desktop\CompassUpdater.cs') (Join-Path $projectRoot 'desktop\WorkbenchNavigation.cs')
if ($LASTEXITCODE -ne 0) { throw '桌面版编译失败。' }
Compress-Archive -LiteralPath $packageDirectory -DestinationPath (Join-Path $projectRoot 'dist\裤装选品桌面版.zip') -Force
Write-Host "桌面版已生成：$exe"
if ($Install) { & (Join-Path $PSScriptRoot 'install_desktop.ps1') -PackageDirectory $packageDirectory -Open:$Open }
