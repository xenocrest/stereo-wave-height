# Case 1 constant-height WASS validation

Run date: 2026-08-11

Status: **END-TO-END COMPLETED; PRE-REGISTERED ACCURACY GATE FAILED**

## 1. Scientific question

Case 1 asks whether a non-zero, known water-surface displacement survives the
complete chain:

```text
synthetic stereo images -> WASS core -> xyzC -> common wassgridsurface grid
  -> independent static Z0 -> H=Z-Z0 -> comparison with known Delta H
```

It is the first non-zero height test. The Case 0 micrometre-scale temporal
result came from nearly identical static reconstructions and is only a zero-field
diagnostic; it cannot answer this question.

## 2. Mathematical truth and selected height

The unified four-frame truth is

\[
H_{true}(x,y,t)=
\begin{cases}
0, & t\in\{0,0.2\}\ \mathrm{s},\\
\Delta H, & t\in\{0.4,0.6\}\ \mathrm{s},
\end{cases}
\qquad \Delta H=+0.010\ \mathrm{m}.
\]

`Delta H` is `SIMULATION_TEST_PARAMETER`, not a real wave height. It was chosen
because 0.010 m is the project's stated centimetre-scale target and is well
above Case 0's `0.000554 m` aligned-grid elevation RMSE. Baseline and working
distance remain fixed at 0.20 m and 2.00 m.

The pre-registered simulation criteria additionally state that a dedicated
sign test should use `|Delta H|>0.010 m`; this run is exactly 0.010 m. Its mean
sign is therefore reported, but it does not independently close that stronger
sign-test requirement. No post-result change of Delta H was made.

## 3. Independent static reference and common transform

All four frames were reconstructed in one WASS run, one autocalibration, one
root `planes.txt`, one gridder setup, and one `config.mat`. The gridder computes
one mean plane from all four rows of `planes.txt`, then uses the same plane
rotation, translation, Z convention, baseline scale, and x/y grid for every
frame.

This is required because independently aligning the static and raised planes to
their own averages could remove the constant displacement. For any common
offset/transform origin C,

\[
(Z_{case1}-C)-(Z_0-C)=Z_{case1}-Z_0.
\]

The static reference uses frames 0 and 1 only:

\[
Z_0(y,x)=\frac{Z(0,y,x)+Z(1,y,x)}{2}.
\]

Frames 2 and 3 are excluded from Z0 and evaluated as

\[
H_{calc}(t,y,x)=Z_{case1}(t,y,x)-Z_0(y,x).
\]

The parser confirmed identical x/y coordinates, `wass_plane_aligned_grid`,
unit m, scale 0.20 m, spacing 0.010 m, and one `[4,160,160]` product before
subtraction.

## 4. Simulation and device parameters

| Parameter | Value | Status/source |
|---|---:|---|
| candidate camera | MER2-503-36U3C | candidate equipment registry |
| image size | 2448 x 2048 px | candidate equipment registry |
| pixel size | 3.45 um | candidate equipment registry |
| nominal focal length | 8 mm | candidate lens |
| nominal fx/fy | 2318.8405797 px | SIMULATION_NOMINAL |
| distortion | zero | ideal_simulation_assumption |
| baseline | 0.20 m | SIMULATION_TEST_PARAMETER |
| working distance | 2.00 m | SIMULATION_TEST_PARAMETER |
| Delta H | +0.010 m | SIMULATION_TEST_PARAMETER |
| truth domain | x [-0.9,0.9] m; y [-0.8,0.8] m | mathematical truth |
| texture seed | 20260811 | deterministic simulation parameter |
| frames | 2 static + 2 raised | unified sequence |

Manifest SHA-256 is
`c21d17a97143576a1015579e48bd4b92f2370468dbadc19f073f0c8cb82ef990`;
truth archive SHA-256 is
`24f554e7dbf13bcc63c209ce7db8f9c157af6eea0c78b85218b76c915180a6aa`.
Neither truth nor generated images were committed.

## 5. WASS core run

Runtime: native Windows WASS `1.11_heads/master-0-g6b82aeb`, MSVC, OpenCV
4.6.0 at `D:\wass\dist\bin`. WASS source was not modified. The Case 0 matcher
and stereo configs were retained unchanged; their hashes are
`bae1e60a...af32` and `79ca52bc...d843`.

All stage return codes were zero:

| Frame/group | matcher inliers | matcher epipolar error (px) | triangulated points | final points |
|---|---:|---:|---:|---:|
| static 000000 | 989 | 0.0453563 +- 0.0877183 | 4,322,503 | 4,311,954 |
| static 000001 | 989 | 0.0453563 +- 0.0877183 | 4,322,503 | 4,311,954 |
| raised 000002 | 1,647 | 0.0315690 +- 0.0471454 | 4,331,598 | 1,794,468 |
| raised 000003 | 1,647 | 0.0315690 +- 0.0471454 | 4,331,598 | 1,794,468 |

Autocalibration loaded 5,272 matches. SBA completed in 18 iterations; final
epipolar error was `0.0204063 +- 0.0666558 px`. Each same-height pair has an
identical final xyzC SHA-256; static and raised hashes differ as required.
The common four-plane mean is
`[-4.96453e-6, 4.26285e-5, 0.999999998, -9.97440618]`; the difference between
raised and static mean plane offsets, multiplied by the 0.20 m baseline, is
`+0.0089960025 m`. This independent plane-level check has the expected sign and
is consistent with the gridded mean without replacing the grid validation.

## 6. Official gridder run

Official `wassgridsurface==0.11.4` used one four-row `planes.txt`, one
`config.mat`, DCT, baseline 0.20 m, fps 5, and the frozen Case 0 grid:

```text
wassgridsurface --action setup <work> <grid> --gridconfig <grid>/gridconfig.txt --baseline 0.20 --fps 5
wassgridsurface --action grid <work> <grid> --gridsetup <grid>/config.mat --interpolation_algorithm DCT --parallel 1 --num_frames 4
```

Both commands returned zero. Setup reported `dx=dy=0.010 m`; x is
`[-0.895,0.695] m` and y is `[-0.795,0.795] m`. NetCDF SHA-256 is
`a1f84f41967cfad5fed2491d23553413e799d216242aecbf7f90cb65d311eb75`.

The raised frames had substantially fewer final plane-filtered points. Their
DCT optimizations ran to the 500-iteration maximum and emitted an all-NaN-slice
warning during initial point-grid aggregation. Although the command succeeded,
the final Z range of approximately -0.070 to +0.078 m is a quality failure
signal consistent with sparse-support DCT ringing. No ROI, DCT parameter,
filter, or interpolation method was changed after seeing the result.

## 7. Metrics and decision

For every valid raised-frame cell,

\[
e=H_{calc}-0.010\ \mathrm{m}.
\]

| Metric | Result | Pre-registered gate | Decision |
|---|---:|---:|---|
| mean recovered height | `0.0088889696 m` | sign positive; mean error <=0.010 m | positive / within mean tolerance |
| signed bias | `-0.0011110304 m` | absolute bias <=0.005 m | pass |
| RMSE | `0.0110795383 m` | <=0.010 m | **fail** |
| MAE | `0.0056565648 m` | <=0.010 m | pass |
| maximum absolute error | `0.0754659262 m` | <=0.030 m | **fail** |
| recovered-height standard deviation | `0.0110236918 m` | report | reported |
| finite-grid coverage | `1.0` | >=0.95 | pass under 0.11.4 DCT finite-Z policy |
| finite-grid hole rate | `0.0` | <=0.05 | pass under same policy |

Recovered range is `[-0.0654659262,+0.0828164995] m`; both raised-frame means
are positive (`0.00888819 m`, `0.00888975 m`). The absolute scale and sign are
visible in the mean, but spatial error violates the frozen RMSE and maximum
error gates. **Case 1 does not formally pass.**

Coverage is finite DCT output coverage, not raw point-support density, because
0.11.4 leaves `maskZ` unwritten and DCT returns a full-domain mask.

## 8. Limits and UNKNOWN/TODO

- Full SHA/tag behind local WASS short commit `6b82aeb`: UNKNOWN.
- Root cause of raised-frame point loss requires a separate, pre-registered
  diagnosis; likely causes must not be selected without evidence.
- Whether official DCT parameters or another official gridder mode should be
  used for sparse point support: TODO and requires review before rerun.
- A dedicated sign test with `|Delta H|>0.010 m`, and negative Delta H: TODO.
- Raw-support-aware coverage/mask definition: TODO.
- Real-camera calibration, synchronization, water optics, and 1 cm real-water
  accuracy remain untested.
- Case 2 was not attempted.

Large images, point clouds, logs, `config.mat`, and `gridded.nc` remain outside
Git at `D:\stereo-wave-height-runs\case1-constant-20260811`.
