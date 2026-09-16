param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$python = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Demo Python missing: $python" }
& $python -c "import streamlit, plotly, plyfile, netCDF4, scipy"
if ($LASTEXITCODE) { throw "Missing UI dependency. Install scripts/requirements_presentation_ui.txt with the demo Python." }
$manifestPath = Join-Path $repo 'presentation_assets/vieira2025_end_to_end_demo/demo_manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Golden Demo asset missing: $manifestPath" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $manifest.outputs.root)) { Write-Warning "Golden Demo asset missing: $($manifest.outputs.root). UI will identify missing files." }
Write-Output 'Read-only Golden Demo v1: http://localhost:8501'
if (-not $NoBrowser) { Start-Process 'http://localhost:8501' }
& $python -m streamlit run (Join-Path $repo 'tools/presentation_demo_ui.py') --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
