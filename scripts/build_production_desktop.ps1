param([string]$OutputRoot='D:\stereo-wave-height-runs\production-desktop-build-20260917')
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$python='D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
& $python -m PyInstaller --noconfirm --onedir --windowed --name StereoWaveHeightSystem --paths (Join-Path $repo 'src') --distpath (Join-Path $OutputRoot 'dist') --workpath (Join-Path $OutputRoot 'build') --specpath $OutputRoot --add-data ((Join-Path $repo 'src/production_app')+';production_source/production_app') --exclude-module streamlit --exclude-module plotly --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtNetwork --exclude-module tkinter --exclude-module IPython --exclude-module torch --exclude-module torchvision --exclude-module tensorflow --exclude-module jax --exclude-module kornia --exclude-module pandas --exclude-module sympy --exclude-module numba --hidden-import PySide6.QtTest (Join-Path $repo 'tools/production_desktop.py')
if ($LASTEXITCODE) { throw '正式桌面程序打包失败' }
$bundle=Join-Path $OutputRoot 'dist/StereoWaveHeightSystem'
# Avoid the known ICU-78 / system ICU name collision; no system DLL changed.
$icuCollision=Join-Path $bundle '_internal/icuuc.dll'
if (Test-Path -LiteralPath $icuCollision) {
    Move-Item -LiteralPath $icuCollision -Destination (Join-Path $OutputRoot 'icuuc_scientific_dependency_not_deployed.dll') -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $bundle 'config') | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'config/production_toolchain.json') -Destination (Join-Path $bundle 'config/production_toolchain.json')
$qtRuntime='D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Lib\site-packages\PySide6'
# GUI provenance reads version metadata but does not import these solvers.
$site=Split-Path $qtRuntime -Parent
foreach ($package in @('wassgridsurface','wassncplot')) {
    $metadata=Get-ChildItem -LiteralPath $site -Directory -Filter ($package+'-*.dist-info')
    if ($metadata.Count -ne 1) {throw ('官方工具版本 metadata 不唯一：'+$package)}
    Copy-Item -LiteralPath $metadata.FullName -Destination (Join-Path $bundle '_internal') -Recurse -Force
}
foreach ($name in @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','msvcp140_codecvt_ids.dll','concrt140.dll')) {
    Copy-Item -LiteralPath (Join-Path $qtRuntime $name) -Destination (Join-Path $bundle '_internal') -Force
}
foreach ($name in @('USER_GUIDE_ZH.md','ARCHITECTURE_ZH.md','PRODUCTION_V1_REPORT_ZH.md')) {
    if (Test-Path -LiteralPath (Join-Path $repo $name)) {Copy-Item -LiteralPath (Join-Path $repo $name) -Destination $bundle}
}
$target=Join-Path $repo 'dist/StereoWaveHeightSystem'
if (Test-Path -LiteralPath $target) {
    $resolvedTarget=(Resolve-Path -LiteralPath $target).Path
    $expectedTarget=[IO.Path]::GetFullPath((Join-Path $repo 'dist/StereoWaveHeightSystem'))
    if ($resolvedTarget -ne $expectedTarget) {throw '部署目标路径校验失败'}
    Move-Item -LiteralPath $resolvedTarget -Destination (Join-Path $OutputRoot ('retained-production-'+[Guid]::NewGuid().ToString('N')))
}
Copy-Item -LiteralPath $bundle -Destination $target -Recurse
Write-Output "正式桌面程序构建完成：$target"
