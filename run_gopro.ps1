$ErrorActionPreference = 'Stop'
$Python = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
$Config = if ($args.Count -gt 0) { $args[0] } else { "$PSScriptRoot\pipeline\config.example.yaml" }
& $Python "$PSScriptRoot\pipeline\run_pipeline.py" $Config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

