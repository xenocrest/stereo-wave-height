# Windows Offline Demo Packaging

Classification: `WINDOWS_OFFLINE_DEMO_PACKAGE_COMPLETED`  
Freeze: `DEMO_DISTRIBUTION_FROZEN`

## Feasibility and selected design

The lowest-risk successful design is Solution A: PyInstaller 6.22.2 `--onedir`. The GUI and frozen Python backend are packaged in one `StereoWaveHeightDemo.exe`. GUI reconstruction launches the same executable with `--backend-single-frame <config>` in a worker thread, so packaged operation requires neither system Python nor `PYTHONPATH`.

WASS remains an unmodified external executable directory inside `runtime/wass`; the policy-capable stereo executable and required OpenCV DLLs keep their existing file layout. FFmpeg and its shared DLLs remain under `runtime/ffmpeg`. Runtime paths resolve from the executable directory or user-selected files, not repository cwd. No videos are bundled.

## Distribution

- Build command: `powershell -ExecutionPolicy Bypass -File tools/build_demo_windows.ps1`
- Distribution: `D:\research\stereo-wave-height\dist\StereoWaveHeightDemo`
- Executable: `D:\research\stereo-wave-height\dist\StereoWaveHeightDemo\StereoWaveHeightDemo.exe`
- Size: 450,145,893 bytes (429.29 MiB), 1,451 files
- System Python required: no
- Network required: no
- Repository cwd required: no
- External runtime included in distribution: WASS/OpenCV DLLs and FFmpeg shared runtime

`build/`, `dist/`, and generated PyInstaller spec files remain ignored and are not committed.

## Smoke results

The packaged EXE launched from `C:\Windows` and remained responsive. Packaged-resource checks passed for calibration, static reference, canonical mapping, WASS configs, portable FFmpeg, and all four WASS processes. Using packaged runtime paths, calibration loading, calibration preview, 1920×1080/60 fps video reading, play/pause target selection, original/overlay/height/status display, OBSERVED/ESTIMATED/UNSUPPORTED queries, point-cloud dependencies, and session export passed without repo-relative resources.

One and only one packaged backend run used HomeTank_004 Wave at `29.4654055 s`:

- Status: `SINGLE_FRAME_DENSE_HEIGHT_COMPLETED`
- XYZ points: 35,459
- Packaged backend total: 32.6401 s
- Packaged process wall time including executable startup: 40.320 s
- Development demo backend reference: 30.5388 s

The packaged backend time is within the same approximately-30-second operating class; no performance tuning was performed.

## Packaging fixes only

- Added executable-directory resource/runtime/session resolution.
- Added same-EXE packaged backend command dispatch.
- Made runtime-binding executable paths portable relative to the binding JSON.
- Preserved absolute paths when external GUI request configs are copied into session directories, including portable FFmpeg.

No calibration, synchronization, WASS, XYZ, height, pixel–XYZ, MLS, observation-gate, ROI, or dense-policy algorithm changed.
