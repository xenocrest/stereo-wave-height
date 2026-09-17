param([string]$OutputRoot='D:\stereo-wave-height-runs\presentation-desktop-build-20260916')
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$python='D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
& $python -m PyInstaller --noconfirm --onedir --windowed --name StereoWaveHeightDemo --paths (Join-Path $repo 'tools') --distpath (Join-Path $OutputRoot 'dist') --workpath (Join-Path $OutputRoot 'build') --specpath $OutputRoot --add-data ((Join-Path $repo 'presentation_assets/vieira2025_end_to_end_demo/demo_manifest.json')+';presentation_assets/vieira2025_end_to_end_demo') --exclude-module streamlit --exclude-module plotly --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtNetwork --exclude-module tkinter --exclude-module IPython --exclude-module torch --exclude-module torchvision --exclude-module tensorflow --exclude-module jax --exclude-module kornia --exclude-module cv2 --exclude-module pandas --exclude-module sympy --exclude-module numba --hidden-import PySide6.QtTest (Join-Path $repo 'tools/presentation_demo_desktop.py')
if ($LASTEXITCODE) { throw '桌面打包失败' }
$bundle=Join-Path $OutputRoot 'dist/StereoWaveHeightDemo'
# Scientific dependency discovery may collect ICU 78 as icuuc.dll. Qt on
# Windows uses the system ICU API instead; this namesake shadows it and lacks
# ucnv_open, causing QtCore import failure. Exclude only this proven collision.
$icuCollision=Join-Path $bundle '_internal/icuuc.dll'
if (Test-Path -LiteralPath $icuCollision) {
    Move-Item -LiteralPath $icuCollision -Destination (Join-Path $OutputRoot 'icuuc_scientific_dependency_not_deployed.dll') -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $bundle 'config') | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'config/presentation_demo.json') -Destination (Join-Path $bundle 'config/presentation_demo.json')
# Qt ships a newer compatible MSVC runtime than the Python bootstrap DLLs.
# Use one coherent set at the loader's first search location (no system changes).
$qtRuntime='D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Lib\site-packages\PySide6'
foreach ($name in @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','msvcp140_codecvt_ids.dll','concrt140.dll')) {
    Copy-Item -LiteralPath (Join-Path $qtRuntime $name) -Destination (Join-Path $bundle '_internal') -Force
}
Write-Output "桌面程序构建完成：$bundle"
