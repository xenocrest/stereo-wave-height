# HomeTank_004 Offline Demo GUI — Stage 2

## Classification and freeze

- `DEMO_GUI_STAGE2_COMPLETED`
- `DEMO_SYSTEM_MVP_COMPLETED`
- `BACKEND_FROZEN_FOR_DEMO_INTEGRATION`
- `DEMO_SYSTEM_MVP_FROZEN`

No WASS execution was performed for Stage 2. The GUI reads the previously completed `29.4654055 s` measurement and does not modify calibration, synchronization, WASS, XYZ, height, pixel–XYZ, MLS, observation-gate, or hole-support logic.

## Completed interactions

- Four display modes: original frame, height overlay, height map, and status map.
- Height overlay defaults to 45% alpha and has a 0–100% slider. Only valid OBSERVED/ESTIMATED pixels are colored; UNSUPPORTED pixels retain the original frame.
- Letterbox-aware canvas coordinates map to canonical-cam1 pixels.
- Hover shows pixel, status, source, H, and available XYZ without invoking the backend.
- OBSERVED XYZ comes from the frozen pixel–XYZ artifact through the frozen canonical-to-rectified mapping and 2 px direct-observation gate.
- ESTIMATED H is shown as `SURFACE_ESTIMATED`; its XYZ remains N/A because the frozen dense NPZ does not persist estimated XYZ.
- Matplotlib displays only the original WASS XYZ point cloud in a separate rotatable/zoomable window, with deterministic display subsampling capped near 30,000 points.
- Measurement history remains available after playback and restores overlay, summary, hover, and point-cloud access.
- Exit offers export all, selective export, delete all, or cancel. Export uses staging followed by an atomic directory rename; temporary data is deleted only after a successful export.

## Frozen Case 2 smoke

| Pixel | Status | Source | H | XYZ |
|---|---|---|---:|---|
| `(799,396)` | `UNSUPPORTED` | `UNSUPPORTED` | N/A | N/A |
| `(801,402)` | `OBSERVED` | `DIRECT_STEREO` | `-24.452 mm` | `(-0.061299, -0.062320, 0.255661) m` |
| `(795,418)` | `ESTIMATED` | `SURFACE_ESTIMATED` | `-24.522 mm` | N/A |

The GUI window, four display modes, all three hover identities, original point-cloud window, history reopening, and four-option exit dialog passed the Stage 2 smoke. Selective export and exported-manifest reloading are covered by non-window tests.

## Export contents

Each selected measurement can include the selected frame, generated overlay, height map, status map, original WASS PLY/XYZ, dense NPZ, pixel–XYZ NPZ, unified result JSON, report, and a compact measurement manifest. The session manifest records session identity, camera models, calibration reference, classifications, height summaries, and artifact names.

## Known limitations

- Estimated XYZ is not persisted by the frozen dense artifact and is therefore displayed as N/A.
- The point-cloud viewer is a lightweight scatter view, not a measurement/analysis tool.
- Overlay colormap and layout are functional rather than presentation-polished.
- No executable packaging, automatic ROI, or live professional-camera input is included.
