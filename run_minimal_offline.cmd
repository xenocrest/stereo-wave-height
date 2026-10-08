@echo off
pushd "%~dp0"
"D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe" -m minimal_app.main %*
popd
