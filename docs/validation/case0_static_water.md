# Case 0 Static-Water WASS Validation

Run date: 2026-08-11

Status: **CASE 0 CLOSED THROUGH OFFICIAL WASS REGULAR GRID**

## Scope and runtime

This run validates the path

`ideal static truth -> synthetic stereo PNG -> prepare -> match -> autocalibrate -> stereo -> mesh_cam.xyzC`.

The external runtime is the existing native Windows build at
`D:\wass\dist\bin`, version `1.11_heads/master-0-g6b82aeb`, MSVC Release with
OpenCV 4.6.0. WASS source and binaries were not modified. Run data is retained
outside Git at `D:\stereo-wave-height-runs\case0-static-20260811`.

Case 1 and Case 2 were not entered.

## Simulation test geometry

| Parameter | Value | Unit | Status/source |
|---|---:|---|---|
| camera model | MER2-503-36U3C | — | candidate equipment config |
| image size | 2448 x 2048 | px | candidate equipment config |
| pixel size | 3.45 | um | candidate equipment config |
| nominal focal length | 8 | mm | candidate lens config |
| nominal `fx=fy` | 2318.8405797101445 | px | `8 mm / 0.00345 mm` |
| principal point | `(1223.5, 1023.5)` | px | ideal simulation centre assumption |
| baseline `B` | 0.20 | m | `SIMULATION_TEST_PARAMETER` |
| working distance `Z` | 2.00 | m | `SIMULATION_TEST_PARAMETER` |
| distortion | `[0,0,0,0,0]` | — | ideal simulation assumption |

Neither baseline nor working distance is a confirmed hardware choice.

The nominal static disparity is

```text
d = f B / Z = 2318.8405797101445 * 0.20 / 2.00
  = 231.88405797101447 px.
```

`B/Z=0.10` matches the WASS paper-derived deployment-ratio guidance already
recorded by this project. The expected horizontal overlap fraction for the
parallel ideal cameras is

```text
1 - d / 2448 = 0.9052761201 (90.53%).
```

The convergence/ray-angle scale is

```text
2 atan(B/(2Z)) = 5.7248 degrees.
```

These values give a large common view, disparity well inside the old successful
runtime's 1–640 px search range, and a non-degenerate baseline without claiming
an optimized hardware design.

## Synthetic data

Two static frames were generated with `H_true=0 m` at timestamps 0 and
200,000,000 ns. Surface samples cover `x=[-0.9,0.9] m` with 901 samples and
`y=[-0.8,0.8] m` with 801 samples. Texture seed is `20260811`; splat radius is
1 px. These are simulation parameters.

Observed image checks:

| Check | Result |
|---|---:|
| image encoding | mono8 PNG |
| image shape | 2048 x 2448 |
| intensity range | 0–239 |
| non-zero fraction, each view | 0.77455209 |
| measured best integer horizontal shift | 232 px |
| theoretical disparity | 231.8841 px |
| PNG size, first left/right | 959,267 / 960,099 bytes |

Both frames use the same physical texture and are deliberately identical in
time because Case 0 is static.

## OpenCV XML

The project generated four files with the schema observed in the previous
successful `D:\WASS_DATA` run:

- root `opencv_storage`;
- matrix node `intrinsics_penne`;
- `type_id="opencv-matrix"` and `dt=d`;
- intrinsic shape 3 x 3;
- distortion shape 5 x 1.

The intrinsic matrix is

```text
K = [[2318.8405797101445, 0, 1223.5],
     [0, 2318.8405797101445, 1023.5],
     [0, 0, 1]].
```

Structural comparison with all four old successful XML files matched. Prepare
subsequently read the generated XML successfully. SHA-256 examples:

- `intrinsics_00.xml`: `210E2BA3B6FF1FBD544479B2CB942F4FFD6073C7BB103273B667321CD900012F`;
- `distortion_00.xml`: `639AA79C9B9507EFCFE636AC60F26326969C85C01F5EBE1BED40A151C3A3EA84`.

Zero distortion is not a statement about the candidate lens.

## Matcher and stereo configuration

`matcher_config.txt` is a byte-equivalent derivation of the existing generated
reference at `D:\wass\dist\bin\matcher_config.txt`; no matcher threshold was
changed. SHA-256 is
`BAE1E60A3680BC0193628C35BFFB7FD68BA5E8C672F12A489284BD25B25EAF32`.

Only four existing stereo keys were activated/changed:

| Parameter | Old generated default | Case 0 | Basis |
|---|---:|---:|---|
| `MIN_DISPARITY` | 1 px | 160 px | lower than expected 231.884 px |
| `MAX_DISPARITY` | 640 px | 320 px | higher than expected; 160 px span is divisible by 16 |
| `TRIANG_MIN_ANGLE` | 20 deg | 3 deg | below the explicit 5.7248 deg simulation ray angle |
| `RANDOM_SEED` | -1/system time | 20260811 | repeatable plane RANSAC |

All reconstruction bounds remain disabled (`-1`). Window, uniqueness,
morphology, Z-gap, plane RANSAC, plane distance, and dense settings were not
relaxed. Stereo config SHA-256 is
`79CA52BCDE7612C25A40C62412411DDDB679CA8D0DEA056CD3DC5BD46F14D843`.

## Commands and stage results

The executed command forms were:

```text
wass_prepare --workdir <frame_wd> --calibdir <case0_config> --c0 <cam0.png> --c1 <cam1.png>
wass_match <matcher_config.txt> <frame_wd>
wass_autocalibrate <workdirs.txt>
wass_stereo <stereo_config.txt> <frame_wd>
```

| Stage | Return code | Result |
|---|---:|---|
| prepare frame 0 | 0 | XML read; 2448 x 2048 undistorted images written |
| prepare frame 1 | 0 | same |
| match frame 0 | 0 | 981 inliers; epipolar error `0.125822±0.119506 px` |
| match frame 1 | 0 | 989 inliers; epipolar error `0.045356±0.087718 px` |
| autocalibrate | 0 | 1970 matches; SBA epipolar error `0.035408±0.084145 px` |
| stereo frame 0 | 0 | 4,313,574 filtered points |
| stereo frame 1 | 0 | 4,313,574 filtered points |

Prepare logged missing optional `ext_R.xml`/`ext_T.xml` and continued normally;
match/autocalibrate then produced them. It also logged a missing optional
`prepare_config.txt`. Neither condition caused a non-zero return.

The first match was initially launched through a parent session that timed out
while the child continued. To obtain an unambiguous return code and consistent
final artifacts, it was rerun explicitly; autocalibrate and both stereo frames
were then rerun. The table describes the final consistent run.

## Real WASS 3-D output

Both frames produced actual WASS `mesh_cam.xyzC` files. The final SHA-256 is
identical for both:

`D4DB73A3C19A3654F6EDC59E45E8B6A7669DD7C075CC03D143AE3C418E97F7E4`.

The confirmed loader schema is:

1. one little-endian `uint32` point count;
2. six little-endian `double` quantization limits;
3. 3 x 3 `double` inverse rotation;
4. three `double` inverse-translation values;
5. 3 x N `uint16` quantized coordinates.

The project parser reproduces the colocated WASS MATLAB loader: componentwise
dequantization followed by inverse rigid transformation. No triangulation is
implemented by the project.

## Scale and coordinate validation

Autocalibrate returns `||ext_T||=1`, confirming baseline-normalized WASS
coordinates. The declared simulation baseline therefore supplies the explicit
scale:

```text
metres_per_WASS_unit = B / ||ext_T|| = 0.20 m.
```

The fitted plane distance is `9.9962423429` WASS units, hence
`1.9992484686 m`, differing from the declared 2.00 m working distance by
`-0.0007515314 m`. This agreement independently checks the scale direction.

Plane alignment uses the exact `load_camera_mesh_and_align_plane.m` rotation,
translation, explicit scale, and Z-axis inversion. On each frame:

- static-plane RMSE about aligned `Z=0`: `0.0009598724 m`;
- maximum absolute plane residual: `0.0077325801 m`.

The aligned coordinate system is therefore identified as the WASS fitted-plane
frame, scaled to metres, with positive Z set by the loader's inversion. It is a
simulation static-reference frame, not a surveyed laboratory world frame.

## Static reference, H, and metrics

The two final point-cloud files and decoded XY arrays are exactly identical.
Therefore a valid temporal mean exists on this run's common irregular point
support:

```text
Z0_i = mean_t Z_i(t)
H_i(t) = Z_i(t) - Z0_i.
```

Point-support diagnostics are:

| Metric | Result |
|---|---:|
| H RMSE | 0 m |
| H MAE | 0 m |
| H maximum absolute error | 0 m |
| coverage vs full 2448 x 2048 image | 0.86039106 |
| hole rate vs full image | 0.13960894 |

These zero temporal errors are expected because the two synthetic frames are
identical; they do not measure robustness to temporal noise. The non-zero
static-plane residual above is the meaningful spatial reconstruction diagnostic.

The zero values above remain **irregular common-point diagnostics** only. They
are not the formal Case 0 result because the two `xyzC` files are identical and
the same samples define their temporal mean.

## Official regular-grid closure

The official companion tool `wassgridsurface==0.11.4` was installed in an
isolated runtime outside Git. Its wheel SHA-256 is
`eebf61ee2a4ff59db96f648d5378be50c87c63df65af8f943b44e6dae4322732`.
Full provenance and schema are recorded in
[wassgridsurface integration](../wass/wassgridsurface_integration.md).

The official DCT path produced a verified `gridded.nc` with shape
`[2,160,160]`. The project adapter maps it to `Z[time,y,x]` in metres on:

- x extent `[-0.895, 0.695] m`, increasing, `dx=0.010 m`;
- y extent `[-0.795, 0.795] m`, increasing, `dy=0.010 m`;
- coordinate system identifier `wass_plane_aligned_grid`;
- positive Z normal to the fitted static plane after official Z inversion.

The actual 0.11.4 DCT output leaves `maskZ` entirely at the NetCDF fill value.
Source inspection confirms that DCT returns an all-one mask and this release
does not write it. This run therefore uses the explicit version-scoped policy
`finite_z_for_dct_0_11_4`; all 51,200 Z samples are finite.

The existing `valid_temporal_mean`, `calculate_height`, and metrics functions
give the formal regular-grid results:

| Metric | Result |
|---|---:|
| H RMSE | `0.0000044625202 m` |
| H MAE | `0.0000035309726 m` |
| H maximum absolute error | `0.0000122763813 m` |
| finite-grid coverage | `1.0` |
| finite-grid hole rate | `0.0` |
| aligned Z elevation RMSE about truth `Z=0` | `0.0005541094 m` |
| aligned Z elevation MAE | `0.0004948676 m` |
| aligned Z elevation maximum absolute error | `0.0010604991 m` |
| temporal-mean Z0 RMSE about zero | `0.0005540914 m` |

The non-zero H metrics measure official DCT numerical repeatability. `Z` here
is plane-relative elevation, not optical depth. The independent plane-distance
estimate is `1.9992484686 m` against the 2.00 m simulation distance: error
`-0.0007515314 m`, absolute error `0.0007515314 m`.

## Output inventory

Confirmed output includes undistorted images, feature images, `matches.txt`,
`matcher_stats.csv`, `ext_R.xml`, `ext_T.xml`, `H.xml`, camera poses,
`P0cam.txt`, `P1cam.txt`, disparity diagnostics, `plane.txt`,
`plane_refinement_inliers.xyz`, `scale.txt`, `stereo_config.txt`,
`wass_stereo_log.txt`, and `mesh_cam.xyzC`.

No run images, point clouds, or other large artifacts are committed to Git.

## Conclusion and remaining TODO

Case 0 has passed both the WASS core reconstruction gate and the official
regular-grid height-product gate. All core stages and `wassgridsurface` returned
zero, and the verified NetCDF was consumed by the existing height chain.

Remaining items:

1. improve the Case 0 design to include independently generated static frames if
   temporal repeatability, rather than deterministic reproducibility, is to be
   measured;
2. define a mask/support policy for other gridder versions or interpolation
   modes before use;
3. retain Case 1 and Case 2 as NOT_ATTEMPTED in this task.

This run is ideal simulation only. It excludes real camera noise, calibration
error, synchronization error, reflection/refraction, and real water optics. It
does not demonstrate real-device or real-water 1 cm performance.
