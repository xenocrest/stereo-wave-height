param([switch]$Rebuild, [switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$assets = Join-Path $repo 'presentation_assets/vieira2025_end_to_end_demo'
$python = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
$manifest = Get-Content (Join-Path $assets 'demo_manifest.json') -Raw | ConvertFrom-Json
if ($Rebuild) {
    $newRun = 'D:\stereo-wave-height-runs\vieira-demo-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    New-Item -ItemType Directory -Path $newRun | Out-Null
    $sync = Join-Path $newRun 'sync'
    & $python (Join-Path $repo 'tools/vieira_tlcc_sync.py') --left $manifest.source_left_video --right $manifest.source_right_video --ffmpeg 'D:\FormatFactory\ffmpeg.exe' --praat $manifest.sync.praat --output $sync --start-s 20 --output-fps 10 --frame-count 5
    if ($LASTEXITCODE) { throw 'TLCC failed' }
    $cfg = Get-Content (Join-Path $assets 'chain_config.json') -Raw | ConvertFrom-Json
    $cfg.sync = $sync
    $cfg.output = Join-Path $newRun 'chain'
    $cfg.stereo_config = Join-Path $assets 'official_stereo_config.txt'
    $request = Join-Path $newRun 'request.json'
    $cfg | ConvertTo-Json | Set-Content $request -Encoding utf8
    & $python (Join-Path $repo 'tools/vieira_demo_chain.py') --config $request
    if ($LASTEXITCODE) { throw 'Official chain failed' }
    & $python (Join-Path $repo 'tools/vieira_demo_audit.py') --root $cfg.output
    if ($LASTEXITCODE) { throw 'Output audit failed' }
    Write-Output "New results: $($cfg.output). Overlay review still required; no automatic scientific PASS."
} else {
    $audit = Get-Content (Join-Path $assets 'output_audit.json') -Raw | ConvertFrom-Json
    $audit.query | Format-List
    Write-Output "Frozen full outputs: $($manifest.outputs.root)"
    if (-not $NoOpen) {
        Invoke-Item (Join-Path $assets 'overlay.png')
        Invoke-Item (Join-Path $assets 'height_map.png')
    }
}
