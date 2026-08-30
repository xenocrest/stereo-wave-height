# Stereo Wave Height Offline Demo

## Development mode

```powershell
$env:PYTHONPATH="$PWD;$PWD\src"
python -m application
```

## Packaged mode

Open `dist\StereoWaveHeightDemo` and double-click `StereoWaveHeightDemo.exe`.

- The program is fully local and does not require network access.
- Load the calibration YAML, then select LEFT/RIGHT calibration or measurement videos from local storage.
- A selected single-frame reconstruction takes approximately 30 seconds.
- Keep the complete distribution folder together; WASS and FFmpeg are stored under `runtime\`.
- Raw HomeTank_004 videos are not included in the distribution.
