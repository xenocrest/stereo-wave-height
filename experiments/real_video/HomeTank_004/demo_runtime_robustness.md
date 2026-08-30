# Demo Runtime Robustness

Classification: `DEMO_RUNTIME_ROBUSTNESS_PASS`

## User failure root cause

The packaged session `20260830-162424`, target `26.20519693654267 s`, was found. WASS prepare, match, dense stereo, triangulation, plane extraction, and `mesh_cam.xyzC` output all completed. The project then decoded captured WASS process output as strict UTF-8 and raised:

`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd0 in position 56: invalid continuation byte`

The failure was therefore an engineering log-decoding bug after successful core reconstruction, not insufficient frame support. WASS output is now captured as bytes and decoded with explicit replacement while the complete UTF-8 diagnostic log remains available. WASS-generated text files are read with the same non-destructive policy.

## Bounded fallback and partial results

The GUI adapter now attempts whole synchronized target times in the fixed order `0, -1, +1, -2, +2` source frames. Every candidate re-enters the unchanged synchronization model and moves LEFT and RIGHT together; RIGHT-frame offsets are never searched independently. The first complete result stops the sequence. Metadata records requested/actual time, frame/time offset, fallback status, and earlier failure reasons. Five failures return a bounded Chinese diagnostic.

If XYZ/H exists but optional dense generation fails, the result is retained as `SINGLE_FRAME_RECONSTRUCTION_COMPLETED_DENSE_HEIGHT_FAILED`; the GUI presents the source frame, summary, and point cloud instead of discarding the measurement.

## Failure-case rerun

The original target succeeded directly after the encoding fix, so fallback was not invoked:

- target and actual request: `26.20519693654267 s`
- selected LEFT/RIGHT timestamps: `26.199667 / 26.134033 s`
- pair residual: `-0.2285 ms`
- XYZ and pixel–XYZ: `117,921`
- H: generated
- dense: completed (`5,324` valid ROI heights)
- WASS / dense / total: `23.036 / 4.052 / 27.088 s`

## Playback and process windows

Preview playback now uses a background OpenCV decoder and a single latest-frame slot. Tk polls at 30 fps, replaces one canvas image item, and drops display-only intermediate frames; precise pause measurement still uses the existing backend PTS and R0 synchronization selection. Timeline seeks decode asynchronously. Backend elapsed status remains throttled to 200 ms. Dense and pixel–XYZ data were already loaded once per result and remain cached for hover.

A 10-second HomeTank_004 wave preview produced 274 displayed frames (`27.37 fps`), mean/max display callback work `11.82/17.69 ms`, maximum loop gap `49.30 ms`, and a fixed one-frame buffer with no growing backlog.

Windows child launches now use `CREATE_NO_WINDOW` plus hidden startup info for GUI→backend, FFmpeg, frame selection, single-frame encoding, and WASS. stdout/stderr are still redirected to pipes or log files. No reconstruction algorithm, WASS parameter, calibration, synchronization model, height, MLS, ROI, or dense policy changed.
