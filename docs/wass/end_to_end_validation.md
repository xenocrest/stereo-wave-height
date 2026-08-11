# WASS End-to-End Integration Validation

Validation date: 2026-08-11

## 1. Baseline and outcome

The locked reconstruction baseline is WASS tag `v_1.5`, commit
`59f1b1c46c41a7d0baf85fc2b21e062eaf552feb`; the separately planned gridder is
`wassgridsurface 0.11.4`. Sources are the project reviews in
[`upstream_reference.md`](upstream_reference.md),
[`pipeline_analysis.md`](pipeline_analysis.md), and
[`input_output_spec.md`](input_output_spec.md).

This validation did **not** reach a real WASS reconstruction. On the inspected
Windows host, none of `wass_prepare`, `wass_match`, `wass_autocalibrate`,
`wass_stereo`, or `wassgridsurface` was found on `PATH` or under the inspected
project/D-drive locations. No Linux/Docker WASS runtime was supplied. The
current simulation calibration is `camera.yaml`; it is not a verified OpenCV
XML calibration accepted by WASS v1.5. Therefore Case 0 is blocked before
`wass_prepare`; Cases 1 and 2 were intentionally not attempted. No numerical
height metric is available and no success claim is made.

## 2. Invocation environment

| Item | Recorded value | Status |
|---|---|---|
| Host | Windows, project at `D:\research\stereo-wave-height` | observed |
| WASS core executables | not found | BLOCKED/TODO |
| WASS build/runtime | recommended isolated Linux/Docker baseline | UNKNOWN/TODO |
| `wassgridsurface` executable | not found | BLOCKED/TODO |
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

Baseline and working distance are required explicit simulation parameters. No
final values were selected in this validation because no runnable WASS trial
occurred. Their values are therefore `UNKNOWN/TODO` for the first real run.

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

The adapter deliberately requires caller-supplied, verified WASS XML/config
files. It does not translate simulation `camera.yaml` into OpenCV XML because
the exact v1.5 XML node/container compatibility remains **UNKNOWN/TODO**.

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

The v1.5 source review confirms per-frame outputs including `matches.txt`,
`matcher_stats.csv`, `ext_R.xml`, `ext_T.xml`, `H.xml`, `P0cam.txt`,
`P1cam.txt`, `plane.txt`, `mesh_cam.xyzC`, optional `mesh_cam.xyzbin`/PLY, and
stereo diagnostic logs/images. `wassgridsurface` is expected to produce
`gridded.nc`, but the exact 0.11.4 schema has not been observed on this host.

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

For Case 0, truth is `H_true=0 m`. Because no WASS result exists, RMSE, MAE,
maximum absolute error, coverage, and hole rate are all **NOT_AVAILABLE**.

## 8. Ordered case status

| Case | Status | Reason/result |
|---|---|---|
| Case 0: static water | BLOCKED before prepare | WASS binaries and verified XML/config absent |
| Case 1: fixed height | NOT_ATTEMPTED | Case 0 did not close |
| Case 2: sinusoidal wave | NOT_ATTEMPTED | Cases 0 and 1 did not close |

## 9. Automated verification

Unit tests cover input path mapping, left/right pairing, exclusion of truth,
runner return-code/log handling with a mock process, explicit parser metadata,
and rejection of unknown units and coordinate systems. They do not mock a WASS
reconstruction result and do not count as an integration success.

## 10. UNKNOWN/TODO and next gate

1. Provide/build the locked WASS v1.5 executables in an isolated Linux/Docker
   environment and record compiler, OpenCV, dependency, and executable hashes.
2. Generate `matcher_config.txt` and `stereo_config.txt` using the locked
   binaries' `--genconfig`, then record hashes and water-tank adaptations.
3. Verify exact OpenCV XML node names/container format for candidate nominal
   intrinsics/distortion; validate whether ideal zero distortion is accepted.
4. Select and record Case 0 baseline and working distance as simulation inputs.
5. Determine whether the current sparse point-splat texture provides sufficient
   connected texture for WASS matching; do not change it without a documented
   simulation-model decision.
6. Run Case 0 and archive command logs plus actual output inventory outside Git.
7. Inspect `gridded.nc` with `ncdump -h`; verify 0.11.4 variables/dimensions,
   invalid-value semantics, frame order, coordinate axes, and scale.
8. Verify physical scale using the declared baseline/known geometry before
   converting to metres.
9. Determine the v1.5 procedure for aggregating per-frame `plane.txt` into the
   `planes.txt` required by the gridder.
10. Only after Case 0 metrics exist and pass a predeclared gate, run Case 1;
    only after Case 1 passes, run Case 2.

## 11. Limitations

This is not a real-camera test, contains no real water reflection/refraction or
camera noise, and does not demonstrate real or simulated 1 cm accuracy. It
establishes a fail-fast, provenance-preserving boundary for the future actual
WASS run while keeping WASS itself unchanged.
