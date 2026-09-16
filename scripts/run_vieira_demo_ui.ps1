param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$python = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "演示运行环境缺失：$python" }
& $python -c "import streamlit, plotly, plyfile, netCDF4, scipy"
if ($LASTEXITCODE) { throw "界面依赖缺失。请使用演示 Python 安装 scripts/requirements_presentation_ui.txt。" }
$manifestPath = Join-Path $repo 'presentation_assets/vieira2025_end_to_end_demo/demo_manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "黄金演示文件缺失：$manifestPath" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $manifest.outputs.root)) { Write-Warning "黄金演示文件缺失：$($manifest.outputs.root)。界面会提示具体文件。" }
Write-Output '只读黄金演示第一版：http://localhost:8501'
if (-not $NoBrowser) { Start-Process 'http://localhost:8501' }
& $python -m streamlit run (Join-Path $repo 'tools/presentation_demo_ui.py') --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
