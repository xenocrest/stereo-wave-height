# Case 2 one-dimensional sinusoidal-wave validation

Run date: 2026-08-12

Status: **PASSED PRE-REGISTERED HEIGHT GATES; PHASE OFFSET RECORDED**

## 1. Purpose and truth model

Case 2 is the first end-to-end time-varying surface test:

`analytical truth -> synthetic stereo PNG -> WASS -> xyzC -> official gridder -> independent Z0 -> H -> metrics`.

The one selected truth is

\[
H_{true}(x,t)=A\sin(kx-\omega t+\phi),\quad
k=2\pi/\lambda,\quad \omega=2\pi f.
\]

Parameters are `A=0.010 m`, `lambda=0.80 m`, `f=0.50 Hz`, and `phi=0 rad`.
They are simulation truth, not measured wave parameters.

## 2. Sampling basis

The frozen grid is 160 x 160 with `dx=dy=0.01 m`, spanning 1.60 m in FFT
periodic-sample length. A 0.80 m wavelength therefore has 80 samples and fits
exactly two spatial cycles. This is 40 times the spatial Nyquist minimum.

At 5 Hz, a 0.50 Hz wave has 10 samples per 2.0 s period, five times the
temporal Nyquist minimum. Ten dynamic frames cover one complete discrete
period. Two preceding frames are independent static water and are the only
inputs to `Z0`. Dynamic timestamps are 0.2 s apart; the wave phase time origin
is the first dynamic frame.

## 3. Frozen observation and reconstruction chain

- candidate MER2-503-36U3C: 2448 x 2048 px, 3.45 um pixels;
- candidate 8 mm lens, nominal `f=2318.84 px`, ideal zero distortion;
- baseline 0.20 m and nominal scene distance 2.00 m, both
  `SIMULATION_TEST_PARAMETER`;
- deterministic shared physical texture, seed 20260811;
- official native WASS `1.11_heads/master-0-g6b82aeb`;
- `ZGAP_PERCENTILE=99.5`, all other matcher/stereo values frozen;
- official `wassgridsurface 0.11.4`, DCT, `--parallel 1`, frozen grid;
- no WASS or gridder source modification.

Twelve stereo pairs were generated: two static and ten dynamic. Every frame
was rendered from the analytical 3-D surface through the two pinhole cameras.
Truth height, disparity and point cloud were not copied into the WASS workspace.
Per-image SHA-256 values are retained in the outside-Git run record at
`D:/stereo-wave-height-runs/case2-sinusoidal-20260812`; no PNG, xyzC or NetCDF
is committed.

## 4. WASS and grid results

Prepare, match, autocalibrate, stereo and gridder all returned zero for all 12
frames. Static frames each yielded 4,322,503 triangulations, 4,320,802 retained
points (99.9606%). Across dynamic frames:

- triangulated points: 4,331,598--4,337,716;
- largest-component points: 4,328,196--4,336,815;
- retention: 99.9215%--99.9892%;
- raw observation support on every official grid: 100%;
- validation eligible domain: 100%; finite coverage 100%; hole rate 0%.

The shared `planes.txt`, scale 0.20 m and one grid setup were used for static
and dynamic frames. `Z0` is the valid temporal mean of static frames 000000 and
000001 only. The ten dynamic frames never contribute to the reference.

## 5. Height and wave results

Errors are evaluated only on the formal raw-observation eligible domain.

| quantity | result |
|---|---:|
| signed height bias | -0.2606 mm |
| height RMSE | 5.3968 mm |
| height MAE | 4.7505 mm |
| maximum absolute height error | 10.1320 mm |
| amplitude recovered | 9.6930 mm |
| amplitude error | -0.3070 mm (-3.0695%) |
| wavelength recovered | 0.8000 m |
| wavelength error | <1e-12 m |
| frequency recovered | 0.5000 Hz |
| frequency error | 0 Hz |
| wrapped phase recovered/error | +0.7853 rad / +0.7853 rad (44.99 degrees) |

Amplitude, wavelength, frequency and phase were estimated from the center
physical row `y=-0.005 m`, whose raw eligible mask is 100%. The estimator finds
the dominant positive-spatial/negative-temporal Fourier bin, then fits sine,
cosine and constant terms by least squares. Unit tests first establish exact
recovery on an analytical sampled sinusoid.

The stored x-t products are the unmodified center-row `H_true(x,t)`,
`H_calc(x,t)` and their difference; no cropping or plotting-time correction is
applied. Large arrays remain outside Git.

## 6. Acceptance and interpretation

The frozen gates are RMSE <=10 mm, MAE <=10 mm and maximum error <=30 mm.
All three pass, so **Case 2 passes its pre-registered height-field acceptance**.
Wave-parameter errors were report-only in this first run and no threshold was
added after seeing the data.

The exact wavelength and frequency show that sampled periodic structure and
propagation rate survive the chain. Amplitude is underestimated by 3.07%. The
44.99-degree phase offset is material and remains a TODO for a separately
reviewed coordinate/phase-origin analysis; it is not hidden, corrected, or used
to tune WASS. Current evidence does not distinguish common x-origin/plane
transform effects from reconstruction phase bias. The height result itself
passes, so no failure-category parameter intervention is authorized here.

## 7. Limits

- This is one ideal synthetic wave, not a parameter scan or real-water test.
- Baseline, distance and ZGAP 99.5 are frozen only for this simulation geometry.
- No reflection, refraction, camera noise, lens distortion, synchronization
  error or real calibration uncertainty is represented.
- DCT is numerically rather than bitwise deterministic as documented for Case 1.
- The reported phase offset requires diagnosis before phase-sensitive scientific
  use; no post-hoc phase correction is applied.
