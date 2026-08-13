# Case 2 phase-alignment diagnosis

Run date: 2026-08-13

Status: **CLOSED — ROOT CAUSE A (TRUTH/GRID X-ORIGIN MISMATCH)**

## 1. Problem and mathematical equivalents

The original wrapped phase error was `+0.785287 rad` (44.99 degrees). For
$\lambda=0.80\ \mathrm{m}$, this is equivalent to

$$
\Delta x=\lambda\frac{45}{360}=0.10\ \mathrm{m}.
$$

For $f=0.50\ \mathrm{Hz}$ it is also numerically equivalent to

$$
\Delta t=\frac{45/360}{f}=0.25\ \mathrm{s}.
$$

These are diagnostic candidates, not assumed corrections.

## 2. Estimator self-check and convention

The estimator fits

$$
H=a\sin(\theta)+b\cos(\theta)+c,
\qquad \theta=kx-\omega(t-t_0),
$$

and returns $A=\sqrt{a^2+b^2}$ and
$\phi=\operatorname{atan2}(b,a)$ wrapped to $[-\pi,\pi)$. It reports sine
phase, not cosine phase. FFT selection uses positive spatial and negative
temporal frequency, matching $kx-\omega t$. The phase reference is the supplied
x coordinate and first supplied dynamic timestamp.

Direct input of exact truth on the 160-point, 10-frame evaluation grid recovers
`A=0.010 m`, `lambda=0.80 m`, `f=0.50 Hz`, and `phi=0 rad` to floating-point
precision. Known-phase, x-origin, t-origin and wrap tests pass. Category E is
excluded. The 901-point rendering domain is not an integer-period FFT domain;
it is not used for the formal estimator self-check.

## 3. Spatial-coordinate evidence

Rendering truth uses world-water coordinates:

- x minimum/maximum: `-0.900/+0.900 m`;
- exact origin sample: `0.000 m`;
- spacing: `0.002 m`, increasing;
- coordinates are physical world surface samples.

The parsed official grid has:

- x minimum/maximum: `-0.895/+0.695 m`;
- nearest-zero centre: `-0.005 m`;
- spacing: `0.010 m`, increasing;
- geometric centre: `-0.100 m`.

The frozen grid configuration explicitly sets `area_center_x=-0.10 m`. The
plane rotation is near identity and supplies no 0.10 m x translation. The
traceable mapping for this run is therefore

$$
x_{world}=x_{grid}+0.10\ \mathrm{m}.
$$

Consequently,

$$
\sin(kx_{world}-\omega t)
=\sin(kx_{grid}-\omega t+k\,0.10),
$$

and $k\,0.10=2\pi(0.10/0.80)=\pi/4$. This predicts the observed positive
phase exactly. Category A is confirmed. Category B is excluded as a parser
error because the parser faithfully reports the official grid coordinates.

## 4. Timestamp audit

| frame | timestamp (ns) | dynamic t (s) |
|---:|---:|---:|
| 2 | 400000000 | 0.0 |
| 3 | 600000000 | 0.2 |
| 4 | 800000000 | 0.4 |
| 5 | 1000000000 | 0.6 |
| 6 | 1200000000 | 0.8 |
| 7 | 1400000000 | 1.0 |
| 8 | 1600000000 | 1.2 |
| 9 | 1800000000 | 1.4 |
| 10 | 2000000000 | 1.6 |
| 11 | 2200000000 | 1.8 |

Manifest, truth generator and estimator use the first dynamic frame as $t=0$.
NetCDF records the same 0.2 s cadence; float32 time storage differs only below
one microsecond. Static frames do not enter the dynamic index. No 0.25 s offset
exists. Categories C and D are excluded.

## 5. Controlled candidates

Each candidate was applied alone; reconstructed H was never changed.

| candidate | phase error (rad) | H RMSE (mm) | result |
|---|---:|---:|---|
| none | +0.785287 | 5.3968 | original origin mismatch |
| x +0.10 m | -0.000111 | 0.8617 | independently supported |
| x -0.10 m | +1.570686 | 9.8824 | rejected |
| t +0.25 s | +1.570686 | 9.8824 | rejected |
| t -0.25 s | -0.000111 | 0.8617 | equivalent but absent |
| phase +pi/2 | -0.785509 | 5.3982 | rejected |
| phase -pi/2 | +2.356084 | 12.8921 | rejected |

Only the +0.10 m spatial mapping has numerical and independent configuration
evidence. No combined correction was tried.

## 6. Project-code correction and results

`translate_coordinate_origin_m` now applies only an explicit caller-supplied SI
translation. It does not infer baseline, camera centre, axis or coordinate
relationship. Tests bind this run's documented mapping and verify the
$k\Delta x$ and $-\omega\Delta t$ phase laws. WASS, gridder, H values and all
frozen parameters remain unchanged.

| metric | historical comparison | reference-aligned diagnostic |
|---|---:|---:|
| signed bias | -0.2606 mm | -0.2606 mm |
| RMSE | 5.3968 mm | 0.8617 mm |
| MAE | 4.7505 mm | 0.6934 mm |
| maximum error | 10.1320 mm | 2.5314 mm |
| amplitude | 9.6930 mm | 9.6930 mm |
| wavelength | 0.8000 m | 0.8000 m |
| frequency | 0.5000 Hz | 0.5000 Hz |
| wrapped phase error | +0.785287 rad | -0.000111 rad |

The phase issue is formally closed as an evaluation reference-origin error,
not a WASS reconstruction error. Future datasets must record an explicit
world-to-output-grid transform instead of deriving it from a run document.
Real-camera/world registration remains UNKNOWN until physical calibration.
