# HomeTank_004 coarse geometry reassessment

## Immutable strict result

The strict result remains `CALIBRATION_QUALITY_FAIL`, with
`approved_for_wass=false`. The 1.879% baseline agreement below is a physical
scale sanity check only; it does not repair the 4.38/4.53 px mono RMS, 7.92 px
stereo RMS, 9.51 px symmetric epipolar RMS, or 21.12 px rectified vertical RMS.

## Corrected manual geometry

The previously supplied 0.700/1.900/1.700 m values contained a decimal-place,
factor-of-10 transcription error. The user-corrected values are baseline
0.070 m, cam0 water height 0.190 m, cam1 water height 0.170 m, and pitch 40 deg
for each camera. Thus the measured vertical height difference, cam1 minus
cam0, is -0.020 m. Yaw and roll remain `UNKNOWN`.

The diagnostic OpenCV baseline is 0.0686847116 m. Its absolute difference from
the manual baseline is 0.0013152884 m (1.3153 mm), or 1.87898% of 0.070 m.
Against the documented 5% coarse sanity tolerance this is
`PHYSICAL_BASELINE_SANITY=PASS`: the recovered scale is physically plausible,
not metrically approved.

## Parameter-level assessment

| Item | Evidence | Coarse classification |
|---|---|---|
| K0 | fx 1519.86 px is +14.36% versus assumed 1329 px; fy/fx 0.9909; principal point offset (-65.6,-80.9) px | `USE_WITH_WARNING` |
| D0 | finite but large k2=0.411 and k3=-1.068 from a high-error solve | `DO_NOT_USE` as specification prior; only retained inside Candidate B |
| K1 | fx 1540.82 px is +10.93% versus assumed 1389 px; fy/fx 0.9891; principal point offset (+85.7,+68.6) px | `USE_WITH_WARNING` |
| D1 | finite, with k2=-0.452 and k3=0.445 from a high-error solve | `DO_NOT_USE` as specification prior; only retained inside Candidate B |
| R | orthogonality max error 1.11e-16, det=1, angle 14.6527 deg, no flip | `USE_AS_COARSE_PRIOR` |
| T direction | finite under `X_cam1=R*X_cam0+T`; manual measurements do not independently determine its direction | `USE_WITH_WARNING` |
| T magnitude | 0.0686847 m agrees with measured 0.070 m to 1.879% | `USE_AS_COARSE_PRIOR` for scale plausibility only |

The rotation axis is `[0.88738591, -0.46022181, 0.02724220]` in the OpenCV
left-camera convention. Equal recorded pitch does not imply zero relative
rotation because relative yaw, roll, mounting offsets, and measurement error
remain unmeasured. The calibrated T is
`[-0.05885880, 0.01258794, -0.03308738] m`; its direction cannot be directly
validated from baseline magnitude and the -0.020 m vertical-height difference,
whose measurement convention is not a complete camera-coordinate translation.

## Candidates and export boundary

`SPEC_COARSE` uses specification-derived K, zero-distortion assumptions and the
manual geometry. It is not exportable because equal pitch and baseline
magnitude do not define complete R/T.

`FAILED_CALIB_COARSE` retains the entire diagnostic OpenCV solution. It is
exportable only through the explicit non-metrological coarse adapter and is
`USE_WITH_WARNING`.

`HYBRID_COARSE` uses specification-derived K, zero D, diagnostic R and T
direction, and scales T to exactly 0.070 m using
`T_hybrid=T_calibrated/||T_calibrated||*0.070`. This preserves the confirmed
OpenCV extrinsic convention and is mathematically defined, but remains
`USE_WITH_WARNING`.

Candidates may be compared only on static data. Wave-derived candidate
selection is forbidden. Every export records `approved_for_wass=false`,
`metrological_validity=false`, and purpose
`ALGORITHM_CLOSURE_VALIDATION_ONLY`; WASS autocalibration is disabled. No WASS
process was run in this reassessment.

Next: `STATIC_COARSE_GEOMETRY_SANITY_TRIAL`.

