$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$python = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\pythonw.exe'
Start-Process -FilePath $python -ArgumentList ('"' + (Join-Path $repo 'tools/presentation_demo_desktop.py') + '"') -WindowStyle Hidden
