$ErrorActionPreference = 'Stop'
$Python = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
& $Python "$PSScriptRoot\pipeline\run_pipeline.py" "$PSScriptRoot\examples\hometank004.yaml"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

