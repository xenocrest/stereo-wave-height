# HomeTank_004 WASS Disparity Range Audit

## 1. Scope and frozen evidence

This audit investigates whether the fixed-calibration phone geometry exceeds
WASS's current dense-disparity search range. It does not change calibration,
`K/D/R/T`, rectification (`alpha=0`, zero disparity), plane extraction, source
video, or any formal static result. Wave was not run.

The diagnostic matrix is outside the repository at
`D:/stereo-wave-height-runs/HomeTank_004/disparity-range-audit-20260822`.
Each case uses the same three prepared static pairs. Only
`MAX_DISPARITY`/OpenCV `numberOfDisparities` changes. The 640-pixel control
reproduces all three prior `mesh_cam.xyzC` files byte-for-byte.

Historical statuses remain `CALIBRATION_QUALITY_FAIL`,
`STATIC_VALIDATION_FAIL`, and `approved_for_wass=false`.

## 2. Actual WASS matcher configuration

Source audit of WASS 1.11 `sgbm_dense_stereo()` confirms:

| Setting | Frozen value | Actual use |
|---|---:|---|
| matcher | OpenCV `StereoSGBM` | default `MODE_SGBM` from five-argument `create()` |
| `MIN_DISPARITY` | 1 px | OpenCV `minDisparity` |
| `MAX_DISPARITY` | 640 px | passed as OpenCV `numberOfDisparities`, not merely a post-filter |
| nominal search interval | approximately [1, 641) px | subpixel output may approach 641 px |
| `WINSIZE` | 13 px | SGBM block size |
| `DENSE_UNIQUENESS_RATIO` | 1 | SGBM uniqueness ratio |
| `DENSE_SPECKLE_RANGE` | 16 | SGBM speckle range |
| `DENSE_SPECKLE_WINDOW_SIZE` | -70 | passed unchanged; nonpositive setting |
| texture threshold | none | WASS sets no separate StereoBM-style texture threshold |
| `DENSE_P1_MULT` | 2 | `P1=2*13^2=338` |
| `DENSE_P2_MULT` | 64 | `P2=64*13^2=10816` |
| `DENSE_DISP12MAXDIFF` | -1 | left/right consistency rejection disabled by this setting |
| `DENSE_PREFILTER_CAP` | 60 | SGBM prefilter cap |
| `DENSE_SCALE` | 1.0 | full rectified resolution |

Therefore 640 is classification **A: the disparity-search upper bound**. It is
not a Z-gap, plane, triangulation, or other post-processing limit.

## 3. Geometry calculation

The calibrated baseline is
`B=0.06868471158474378 m`. WASS normalizes this baseline internally, but the
metric relation remains

`d = f_rect * B / Z_rect`,

where `d` is rectified disparity in pixels, `f_rect` is rectified focal length
in pixels, and `Z_rect` is optical-axis depth in metres.

With the frozen alpha-zero rectification, OpenCV produces
`f_rect=3255.979881 px`. Consequently, 640--641 px corresponds to only
`Z_rect=0.34943--0.34889 m`; any closer rectified surface requires disparity
above the configured interval.

HomeTank_004 has no independently measured optical working distance. As a
bounded geometry sanity calculation—not a new calibration—the user-specified
camera heights `0.17--0.19 m` and pitch `40 deg` imply a central-ray distance
`Z approximately h/sin(40 deg)=0.2645--0.2956 m`, hence an expected rectified
disparity of approximately `845.6--756.6 px`. These inputs are
`USER_SPECIFIED`, and the calculation is approximate because camera yaw/roll
and the exact observed surface point are not measured.

The original prepared intrinsics have `fx=1519.863` and `1540.821 px`, but those
values cannot be compared directly with the SGBM interval after alpha-zero
rectification. SGBM operates on images whose new rectified focal length is
3255.980 px.

The 640-pixel control independently shows P95 effective disparity at
`640.554--640.559 px` in all three frames. Theory and data therefore agree that
the current search range is geometrically marginal and clips part of the near
surface.

## 4. Isolated range matrix

The tested `numberOfDisparities` values are 640, 1280, and 2560, all divisible
by OpenCV's required 16. All other configuration files and input hashes are
unchanged. Each WASS process returned code 0; numerical/physical validity is
assessed separately below.

### 4.1 Valid support and disparity

The lossless WASS float disparity is not exported. Statistics are the same
traceable effective rectified disparity diagnostic used in the preceding
static geometry report: valid `precluster_depth.bin` samples reprojected with
the frozen rectification model.

| Num disp | Frame | Valid points | Mean d | Median d | P5 d | P95 d |
|---:|---|---:|---:|---:|---:|---:|
| 640 | 000000 | 216,874 | 585.272 | 639.546 | 262.498 | 640.559 |
| 640 | 000001 | 133,968 | 488.817 | 629.629 | 48.483 | 640.554 |
| 640 | 000002 | 141,950 | 478.108 | 627.580 | 58.623 | 640.554 |
| 1280 | 000000 | 92,829 | 654.513 | 652.628 | 57.060 | 1273.060 |
| 1280 | 000001 | 109,460 | 747.535 | 674.609 | 57.184 | 1281.094 |
| 1280 | 000002 | 120,646 | 735.956 | 673.475 | 31.154 | 1280.268 |
| 2560 | 000000 | 86,301 | 635.828 | 501.762 | 46.601 | 1345.804 |
| 2560 | 000001 | 72,967 | 605.332 | 536.345 | 25.146 | 1718.160 |
| 2560 | 000002 | 81,078 | 522.653 | 429.437 | 23.019 | 1629.635 |

At 1280, P95 again lies at the expanded upper boundary and the valid count does
not increase. At 2560 the distribution broadens, but valid count falls further.
This is inconsistent with a clean recovery of formerly clipped water matches.

### 4.2 XYZ and plane diagnostics

XYZ values below are decoded camera-coordinate metres from the final retained
component. A low plane RMS alone is not acceptance evidence when the recovered
depth has the wrong sign or belongs to a different surface.

| Num disp | Frame | XYZ points | Z median (m) | Z min/max (m) | Plane RMS (mm) |
|---:|---|---:|---:|---|---:|
| 640 | 000000 | 167,581 | 0.290216 | 0.281420 / 0.343543 | 2.249 |
| 640 | 000001 | 33,286 | 0.330105 | 0.328441 / 0.363817 | 2.161 |
| 640 | 000002 | 34,411 | 0.233335 | 0.226365 / 0.248079 | 2.007 |
| 1280 | 000000 | 10,371 | -0.251195 | -0.264284 / -0.184868 | 1.241 |
| 1280 | 000001 | 16,434 | -0.159984 | -0.388706 / -0.153575 | 1.590 |
| 1280 | 000002 | 26,551 | -0.161556 | -0.587861 / -0.152196 | 1.720 |
| 2560 | 000000 | 7,283 | -0.851466 | -1.211558 / -0.597072 | 6.149 |
| 2560 | 000001 | 4,841 | -0.112734 | -0.211965 / -0.104366 | 0.603 |
| 2560 | 000002 | 5,309 | -0.382895 | -1.875771 / -0.363774 | 2.486 |

Both expanded cases reconstruct far fewer retained points and select
physically invalid negative-Z components. They do not stabilize the three
static frames.

## 5. Classification and parameter decision

Audit findings:

1. `MAX_DISPARITY=640` is an active search bound, and the frozen phone geometry
   places much of the accepted disparity at that bound.
2. The controlled 2x/4x expansion does not recover a consistent water surface;
   it expands the ambiguous match space, lowers support, and selects wrong
   components.
3. Therefore range clipping exists, but it is not the sole mechanism behind
   `STATIC_BASELINE_UNSTABLE`.

Final classification: **`OTHER_MATCHING_INSTABILITY`**, with a confirmed
disparity-range-boundary interaction. The data do not justify changing the
formal WASS disparity value: simply increasing `numberOfDisparities` is
rejected by this isolated test.

The next step remains read-only image-domain diagnosis: measure inter-frame
rectified scale/homography drift, vertical residuals, and texture-supported
common area. A future controlled configuration may need a narrower physically
derived interval with a nonzero minimum/offset rather than a larger zero-based
range, but that is a separate reviewed experiment and is not authorized here.
Wave remains prohibited.

The isolated executable uses the same modular OpenCV 4.6 runtime and exactly
reproduces the frozen 640 outputs, but compiler-level equivalence to the old
production executable remains `NOT_ESTABLISHED`.
