# HomeTank_004 Static Frame Geometry Diagnostic

## 1. Problem and frozen scope

The three static frames each contain a millimetre-RMS plane, but their fitted
normal, offset and mean camera-coordinate Z are inconsistent. This diagnostic
reads the existing `FULL_CALIBRATION` outputs only. It does not rerun WASS,
change `K/D/R/T`, rectification, RANSAC, or process wave data.

Historical statuses remain `STATIC_VALIDATION_FAIL`,
`CALIBRATION_QUALITY_FAIL`, and `approved_for_wass=false`.

## 2. Fixed calibration and coordinate-state identity

The following SHA-256 values are identical for workdirs `000000`, `000001`,
and `000002`:

| Per-workdir artifact | SHA-256 |
|---|---|
| `intrinsics_00000000.xml` | `B57CF6D5F8E94DD5B66AE7B58F8C4F53D8627DEDA3F63F5ABA702F657565913B` |
| `intrinsics_00000001.xml` | `A7CB5FFC9AA1717B709E01C7915F243CA7FCEABC8BA574202A082C4797AF798A` |
| `ext_R.xml` | `ABB2B46624F88515744D827F67F4FE977561E5BF867BEFBFACF56C0CEBD47DC5` |
| `ext_T.xml` | `725AD7C97A55731C9DF1A5F9B7427F1466BF35653836B9707405ED22C1F7D3DC` |
| `P0cam.txt` | `1B2AB64637FF1151B52FD6DF295DAD81D1148598F077E1ECBA858FDEF10575BA` |
| `P1cam.txt` | `95673C5C4798AAD4B1F6BEE0C52EAF6034B569D0461016331C68ACDC19A5E213` |
| `Cam0_poseR/T.txt` | `33EF442DC108A4FAE5A0FB972C03318DFB956E82863868F67B3DBEBF150AAACF` / `CFA890F0B472B81664FA270C5D53C43A0B338C08D0230C37E01F1C6D5122BE9D` |
| `Cam1_poseR/T.txt` | `4DBF2048D88819B83B91C96ECAF678D297AD5B9765180A0D9AC48559BD18351E` / `AE5759975FD1414C92996655AD4E85F34E76638E0E768D99A875783B675D7DD6` |
| `stereo_config.txt` | `1E0F95BBF30881BA1E51940414F62D10772427A4074CC8CBE235A549314D3894` |

The shared input distortion files are also single fixed files, with SHA-256
`35D3AFC7E726630124EA7079BAA8BBC41DEF9A09EABB6CE0B83D5C6F9EE55D99`
for cam0 and
`48F28870243209EA87EB28E778B29A0BAB339817039293783E4592F72CBF72D1`
for cam1. Prepare emits the same per-camera intrinsic file for every frame.

Therefore all three stereo calls use the same numerical calibration and the
same camera-coordinate definition.

## 3. WASS state audit

- `prepare`: frame-local image decoding/undistortion; no external-pose
  optimization. Generated intrinsic hashes are identical.
- `match`: produces frame-dependent sparse-match diagnostics and would write a
  pose, but the frozen OpenCV `ext_R/ext_T` files were restored before every
  stereo call. Match poses were not stereo inputs.
- `autocalibrate`: prohibited and not run.
- `stereo`: the same config, projection matrices and camera poses are present in
  every workdir. The log shows deterministic fixed-calibration rectification,
  auto-swap, dense stereo, triangulation, connectivity, and plane extraction;
  it contains no camera-pose optimization.
- `mesh_cam.xyzC`: although WASS uses each fitted plane internally when
  compressing output, the confirmed loader applies the stored inverse transform
  and returns camera coordinates. The centroid comparison below is therefore
  not a comparison of three uncorrected plane-aligned frames.

No frame-dependent WASS calibration or hidden coordinate transform was found.

## 4. Effective rectified-disparity analysis

WASS did not save its lossless float disparity array; the two disparity PNGs
are min/max-normalized renderings and cannot support pixel-valued statistics.
For a traceable numeric diagnostic, each valid `precluster_depth.bin` sample was
reprojected through the unchanged normalized `T`, the same OpenCV
`stereoRectify(alpha=0, CALIB_ZERO_DISPARITY)` model, and WASS's confirmed
left/right auto-swap. These values are **effective rectified disparities of
valid triangulated points**, not a claim that the unsaved raw SGBM array was
decoded.

| Frame | Valid disparity count | Mean (px) | Median (px) | P5 (px) | P95 (px) |
|---|---:|---:|---:|---:|---:|
| 000000 | 216,874 | 585.2716 | 639.5457 | 262.4985 | 640.5586 |
| 000001 | 133,968 | 488.8168 | 629.6289 | 48.4831 | 640.5543 |
| 000002 | 141,950 | 478.1076 | 627.5800 | 58.6234 | 640.5536 |

The P95 value is essentially unchanged and lies near the configured 640 px
search boundary in every frame. In contrast, Frames 1 and 2 contain a much
larger low-disparity tail and have 38.2% and 34.5% fewer valid points than
Frame 0. This is not a uniform disparity translation: different portions of
the disparity/support distribution survive in each frame.

## 5. XYZ centroid and spatial-support comparison

All values are decoded camera coordinates in metres using the unchanged
OpenCV baseline norm `0.06868471158474378 m`.

| Frame | XYZ points | Centroid X | Centroid Y | Centroid Z | X range | Y range | Z range |
|---|---:|---:|---:|---:|---|---|---|
| 000000 | 167,581 | -0.070803 | -0.041049 | 0.290724 | [-0.095565, -0.014401] | [-0.094508, 0.008939] | [0.281420, 0.343543] |
| 000001 | 33,286 | -0.068521 | -0.043386 | 0.331121 | [-0.084888, -0.053210] | [-0.063278, -0.027075] | [0.328441, 0.363817] |
| 000002 | 34,411 | -0.068772 | -0.045802 | 0.233887 | [-0.086173, -0.053590] | [-0.082648, -0.028994] | [0.226365, 0.248079] |

Centroid X changes by only 2.28 mm and Y by 4.75 mm, while centroid Z spans
97.23 mm. At the same time, Frame 1/2 retain only about one fifth of Frame 0's
XYZ count and much narrower X/Y ranges. A common rigid translation would not
produce this simultaneous support contraction, plane-normal rotation and
strongly changed disparity tail.

## 6. Plane overlap

Maximum pairwise normal angle is `12.1664 deg`. Because the planes are not
parallel, they have no single global separation. Their signed closest-origin
distances are `-0.359858`, `-0.366837`, and `-0.345712 m`; pairwise absolute
differences are `6.980`, `14.146`, and `21.126 mm`. The raw `c` coefficient
range remains `13.062 mm`.

This rules out interpreting the result as a single stable plane undergoing only
an XYZ translation.

## 7. Cause classification

Primary classification: **C — `DIFFERENT_VISIBLE_RECONSTRUCTED_REGION`**.

Evidence:

1. fixed calibration, projections, poses and stereo configuration are
   byte-identical, excluding A (`coordinate transform drift`) inside WASS;
2. disparity changes are distributional rather than a common additive offset,
   so pure B (`disparity bias`) is insufficient;
3. valid counts, low-disparity tails, retained counts and X/Y support extents
   change together, directly demonstrating different reconstructed regions.

The near-640 px upper-bound concentration is an important contributing
observation, but this task does not change the disparity range or any WASS
parameter. Source-phone autofocus/electronic stabilization or image-content
matching variation may cause the input-side change, but neither is confirmed by
the available artifacts and remains `UNKNOWN/TODO`.

## 8. Next step

Before any wave run, perform a read-only image-domain comparison using the same
three pairs: quantify rectified vertical residual, image homography/scale drift,
and the intersection of valid disparity support. This can test phone
autofocus/EIS and distinguish image-geometry drift from texture-dependent dense
matching without altering the frozen reconstruction. Wave remains prohibited.
