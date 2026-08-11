# WASS End-to-End Integration Validation

Validation date: 2026-08-11

## 1. Baseline and outcome

The locked reconstruction baseline is WASS tag `v_1.5`, commit
`59f1b1c46c41a7d0baf85fc2b21e062eaf552feb`; the separately planned gridder is
`wassgridsurface 0.11.4`. Sources are the project reviews in
[`upstream_reference.md`](upstream_reference.md),
[`pipeline_analysis.md`](pipeline_analysis.md), and
[`input_output_spec.md`](input_output_spec.md).

Case 0 has now passed the four-stage WASS core pipeline with the bound native
Windows runtime. Two ideal static frames completed prepare, match,
autocalibrate, and stereo with return code 0 and produced identical real
`mesh_cam.xyzC` point clouds. Baseline-normalized scale was validated from
`||ext_T||=1` and the declared simulation baseline. The canonical regular-grid
height product remains pending because `wassgridsurface/gridded.nc` is absent.
Complete parameters, commands, hashes, diagnostics, and limitations are in
[`case0_static_water.md`](../validation/case0_static_water.md).

## 2. Invocation environment

| Item | Recorded value | Status |
|---|---|---|
| Host | Windows, project at `D:\research\stereo-wave-height` | observed |
| WASS core executables | `D:\\wass\\dist\\bin\\wass_*.exe` | CONFIRMED/CALLABLE |
| WASS build/runtime | native Windows, `1.11_heads/master-0-g6b82aeb`, MSVC/OpenCV 4.6.0 | observed local runtime |
| locked v1.5 baseline runtime | not located | UNKNOWN/TODO |
| `wassgridsurface` executable | not found | UNKNOWN/TODO |
| WASS source modification | none | confirmed |

No package, image, source checkout, or large dataset was downloaded during this
work.

## 3. Input source and candidate camera

The intended Case 0 source is the deterministic synthetic dataset documented in
[`synthetic_image_generation.md`](../simulation/synthetic_image_generation.md):
ideal pinhole projection, shared artificial texture, and `H_true=0`. Images are
2448 x 2048 mono8 PNG. Candidate parameters originate from
`configs/equipment/candidate_system.yaml`: MER2-503-36U3C, 3.45 um pixels, and
an 8 mm candidate lens. These are candidate/simulation-nominal values, not
measured calibration.

Case 0 used `B=0.20 m` and `Z=2.00 m`, both explicitly labelled
`SIMULATION_TEST_PARAMETER`; they are not final hardware values. The resulting
nominal disparity was 231.884 px and common horizontal overlap was 90.53%.

## 4. Actual WASS input contract and adapter

The upstream-reviewed dataset convention uses paired `cam0`/`cam1` images and
six-digit sequence identifiers. WASS v1.5 `wass_prepare` accepts explicit
`--workdir`, `--calibdir`, `--c0`, and `--c1` paths. The adapter materializes:

```text
workspace/
  input/cam0/<frame>_<timestamp-ms>_01.png
  input/cam1/<frame>_<timestamp-ms>_02.png
  config/intrinsics_00.xml
  config/intrinsics_01.xml
  config/distortion_00.xml
  config/distortion_01.xml
  config/matcher_config.txt
  config/stereo_config.txt
  work/
  logs/
  wass_input_manifest.json
```

The timestamp token conversion from project nanoseconds to filename
milliseconds must be exact or the adapter fails. Images are copied byte for
byte; no geometry, radiometry, or filename-derived pairing correction occurs.
Ground-truth files are neither read nor copied into the WASS workspace. Every
input/config file is recorded with SHA-256.

The old successful native run confirms OpenCV XML root `<opencv_storage>`, node
name `intrinsics_penne`, 3 x 3 double intrinsic matrices, and 5 x 1 double
distortion vectors. The adapter still requires caller-supplied WASS XML/config
files: converting the simulation nominal camera to these files must be a
separate explicit step and must not reuse the old real-data calibration.

## 5. Actual command sequence

The runner records argv, stdout, stderr, stage, and frame before invoking an
external process without a shell. Based on the locked source review, commands
are:

```text
wass_prepare --workdir <frame_wd> --calibdir <config> --c0 <cam0.png> --c1 <cam1.png>
wass_match <matcher_config.txt> <frame_wd>
wass_autocalibrate <workdirs.txt>
wass_stereo <stereo_config.txt> <frame_wd>
```

All frames complete prepare before match; autocalibration consumes the complete
work-directory list; stereo then runs per frame. A non-zero return code stops
the chain at that stage. Executable paths are mandatory and explicit.

## 6. Actual outputs and parser boundary

The located completed work directory directly confirms per-frame outputs including `matches.txt`,
`matcher_stats.csv`, `ext_R.xml`, `ext_T.xml`, `H.xml`, `P0cam.txt`,
`P1cam.txt`, `plane.txt`, `mesh_cam.xyzC`, optional `mesh_cam.xyzbin`/PLY, and
stereo diagnostic logs/images. `wassgridsurface` is expected to produce
`gridded.nc`, but neither the gridder nor an old `gridded.nc` was found on this host.
The colocated MATLAB loader confirms the `mesh_cam.xyzC` binary field order and
dequantization formula. For Case 0, `||ext_T||=1` plus the declared 0.20 m
simulation baseline confirms `0.20 m` per WASS baseline unit; this confirmation
is run-specific and does not assign units to unrelated historical data.

The new NetCDF parser requires a run-specific mapping proven by `ncdump -h` and
an independent scale check. The caller must specify variable names, exact Z/mask
dimension order, whether true means valid or invalid, source/output units,
coordinate-system identifier, and a
positive scale factor. It explicitly transposes to project `[time,y,x]`, applies
only the declared scale to X/Y/Z, combines the declared mask with finite values,
and pairs frames with manifest timestamps. It fails on UNKNOWN unit or
coordinate metadata. It does not infer axes or parse `mesh_cam.xyzC` because
the compressed representation and physical scale have not yet been verified.

## 7. Height chain and metrics

Once a verified parser produces `StandardizedGrid3D`, the already implemented
chain is:

```text
StandardizedGrid3D
  -> explicit coordinate/unit validation
  -> valid temporal mean Z0(y,x)
  -> H_calc(time,y,x) = Z(time,y,x) - Z0(y,x)
  -> RMSE, MAE, maximum absolute error, coverage, hole rate
```

For Case 0, truth is `H_true=0 m`. On the identical common irregular point
support, temporal-mean H has RMSE/MAE/max error 0 m, coverage 0.860391, and hole
rate 0.139609 versus the full image. Static-plane RMSE is 0.0009599 m and max
absolute residual is 0.0077326 m. These are point-support diagnostics; canonical
regular-grid metrics remain NOT_AVAILABLE.

## 8. Ordered case status

| Case | Status | Reason/result |
|---|---|---|
| Case 0: static water | CORE_PASSED / GRID_PENDING | all four WASS stages returned 0; xyzC scale confirmed |
| Case 1: fixed height | NOT_ATTEMPTED | Case 0 did not close |
| Case 2: sinusoidal wave | NOT_ATTEMPTED | Cases 0 and 1 did not close |

## 9. Automated verification

Forty-three unit tests cover input path mapping, left/right pairing, exclusion
of truth, runner failure/log handling, native/WSL runtime configuration, runtime
probe behavior, explicit parser metadata, and rejection of unknown units and
coordinate systems. A separate live health probe through project code reports
all four local core programs callable. The real WASS run is recorded separately from unit tests; no unit test invokes WASS.

## 10. UNKNOWN/TODO and next gate

1. Full SHA/tag for embedded short commit `6b82aeb` remains UNKNOWN because the
   local source snapshot has no `.git` metadata.
2. Locate or deliberately provision a recorded `wassgridsurface` runtime.
3. Generate and inspect real `gridded.nc`; confirm schema, mask polarity, axes,
   scale, and timestamps.
4. Run the existing canonical `valid_temporal_mean -> HeightField -> metrics`
   chain on that verified grid.
5. Case 1 and Case 2 remain NOT_ATTEMPTED until the Case 0 grid gate decision.

## 11. Limitations

This is not a real-camera test, contains no real water reflection/refraction or
camera noise, and does not demonstrate real or simulated 1 cm accuracy. It
establishes a fail-fast, provenance-preserving boundary for the future actual
WASS run while keeping WASS itself unchanged.
