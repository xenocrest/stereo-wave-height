# Dual stereo reconstruction model

The reconstruction model now has two independent geometry-compatible routes.
The desktop GUI remains frozen while these routes are validated.

1. **Primary — WASS:** retains the existing official WASS reconstruction.
2. **Fallback candidate — calibrated OpenCV StereoSGBM:** rectifies with the
   supplied `K0/D0/K1/D1/R/T`, computes left and right disparities, applies
   left-right consistency, and reprojects accepted disparities with OpenCV's
   metric `Q` matrix.

Both routes implement the rectified stereo relation

\[
Z=\frac{fB}{d}.
\]

The fallback does not fill rejected disparities. A pixel is accepted only when
its disparity is finite, inside the configured search interval, and satisfies

\[
|d_L(u,v)+d_R(u-d_L,v)|\leq\tau_{LR}.
\]

Accepted points are expressed in the rectified left-camera coordinate system
in metres. Height is calculated later from an explicit reference plane using
signed normal distance; camera `Z` is not treated as water height.

This route cannot compensate for invalid calibration. HomeTank_005 currently
has `CALIBRATION_OPERATIONAL_DOMAIN_FAIL`, so it is an integration dataset, not
accuracy evidence. Full water-ROI coverage will be claimed only after direct
stereo support plus a separately validated bounded surface-completion policy
covers every requested pixel. Unsupported values must never be silently
invented.

## Initial HomeTank_005 diagnostic

The frozen 48.0 s pair was evaluated without running or modifying WASS. With a
640 px search interval, only 2,696 of 2,073,600 pixels (0.1300%) passed strict
left-right consistency. Disparity P5/P50/P95 was 0.625/1.1875/639 px and depth
P5/P50/P95 was 0.833/448.164/851.511 m. The distribution is physically
incompatible with the tank scene and reaches the disparity boundary. This is
evidence that changing the stereo implementation alone does not repair the
current calibration/image correspondence. Classification:
`ALTERNATE_BACKEND_IMPLEMENTED__HOMETANK005_GEOMETRY_NOT_VALID_FOR_HEIGHT`.
