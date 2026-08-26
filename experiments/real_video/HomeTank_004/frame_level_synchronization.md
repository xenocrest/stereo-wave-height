# HomeTank_004 Frame-level Synchronization Refinement

## Scope and method

This task only refines the video clock relation. It does not change calibration, WASS, geometry, height, or historical coarse synchronization. Static and wave are independent recordings and therefore receive independent models.

Every decoded frame is measured at its actual PTS. Mean luma is computed after a read-only 64×36 decode; a centered three-frame mean reduces single-frame compression noise. Robust derivative edges retain polarity and use linear half-level interpolation between adjacent PTS only when the local edge is non-zero and monotonic. No nominal-FPS time axis is generated.

The model is

$$
t_R=a t_L+b,
$$

with event residual $r_i=t_{R,i}-(a t_{L,i}+b)$. Offset-only and affine fits are compared. Affine drift is selected only with at least three pairs and at least 20% residual-RMS improvement. This prevents two events from exactly determining an unsupported drift model.

## Evidence and quality gate

The representative frame period is the smaller local median PTS interval, 16.656 ms. Establishment requires at least three matched events, P95 absolute residual no greater than half a frame, and maximum residual no greater than one frame. Half-to-one-frame P95 is reported as a warning but does not authorize WASS under the existing strict backend gate.

| Dataset | Events L/R | Matched | Selected model | $a$ | $b$ (ms) | RMS (ms) | P95 (ms) | Max (ms) | Classification |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| Static | 2 / 10 | 2 | Offset | 1.0 | -20.186 | 9.103 | 9.103 | 9.103 | `FRAME_LEVEL_SYNC_NOT_ESTABLISHED` |
| Wave | 8 / 6 | 5 | Offset | 1.0 | -65.406 | 8.564 | 13.291 | 13.934 | `FRAME_LEVEL_SYNC_WARNING` |

The wave affine candidate had $a=0.999978519$, $b=-65.910$ ms, and RMS 8.278 ms. Its 3.3% improvement is below the predeclared 20% material-improvement rule, so the simpler offset model is retained. Static has only two matched events and cannot independently support drift.

## Target-pair diagnostics

| Dataset | Requested left | Actual left PTS | Actual right PTS | Pair residual | Backend gate |
|---|---:|---:|---:|---:|---|
| Static | 10.012256 s | 10.012256 s (`901103`) | 10.000267 s (`900024`) | +8.197 ms | blocked |
| Wave | 20.000000 s | 20.001878 s (`1800169`) | 19.933867 s (`1794048`) | -2.606 ms | blocked |

The small wave target residual is not sufficient by itself: nearest-frame selection mathematically tends to produce a residual within half a frame. Model uncertainty must also pass. Here, global-luma event P95 remains 0.798 frame and the fixed-light ROI has not been independently registered. The honest overall result is therefore `FRAME_LEVEL_SYNC_NOT_ESTABLISHED`; WASS was not run for either sample.

## Remaining requirement and boundary

A manually verified fixed-light ROI on both camera views, or hardware trigger/timestamps in the future professional system, is required to strengthen the evidence. The current result is not a reconstruction failure.

Ruler data was not read and remains completely downstream of reconstruction. No MP4, extracted frame, point cloud, or WASS workspace is committed.
