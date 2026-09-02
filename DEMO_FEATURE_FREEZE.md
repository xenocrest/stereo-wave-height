# Presentation Demo Feature Freeze

Status: `DEMO_FEATURES_FROZEN`

The Windows offline presentation path is frozen after the final packaged end-to-end acceptance on 2026-09-02:

`demo calibration → wave video pair → common FOV → water ROI → reference solve → measurement solve → dense height result → overlay / hover / point cloud / history / export`.

The accepted executable is `dist/StereoWaveHeightDemo/StereoWaveHeightDemo.exe`. It operates in presentation-only estimation mode for HomeTank_005. The calibration remains geometry-unverified, the reference/current reconstructed planes are not a validated invariant cross-frame coordinate system, and physical accuracy is not established. The demo therefore presents a bounded current-frame relative surface-shape field with explicit `OBSERVED`, `ESTIMATED_LOCAL`, and `ESTIMATED_GLOBAL_MODEL` provenance.

From this freeze onward, presentation work is limited to blocking bug fixes. New workflow features are out of scope. Calibration/model research and accuracy improvement must preserve the frozen user path and its artifact provenance.

The ruler and any manually expected height remain independent validation inputs and are not used by WASS, reconstruction, or height computation.
