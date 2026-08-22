# HomeTank_004 calibration validation

## Calibration-first principle

Calibration parameters are the primary source for stereo reconstruction.
Manual measurements are used only for independent physical sanity validation.
They must not replace calibrated K/D/R/T when the calibration solution is the
candidate under evaluation.

The calibration path was checkerboard observation -> OpenCV official calib3d
calibration -> K0/D0/K1/D1/R/T. These parameters are prepared for the next
static-only reconstruction trial; no WASS process was run here.

## Independent baseline validation

The calibrated baseline is 68.6847 mm and the corrected manual measurement is
70.0000 mm. Their absolute difference is 1.3153 mm, or 1.87898% of the manual
measurement. Therefore `baseline_validation=PASS`: the calibrated baseline is
physically consistent with the independent measurement.

This pass is not a calibration quality pass. The strict metrics remain:

| Metric | Result |
|---|---:|
| stereo RMS | 7.922425 px |
| symmetric epipolar RMS | 9.508413 px |
| rectified vertical RMS | 21.122547 px |

The calibration remains `CALIBRATION_QUALITY_FAIL`, is not metrological, and
has `approved_for_wass=false`. Its engineering interpretation is
`PHYSICALLY_CONSISTENT_BUT_NOT_METROLOGICAL`.

Candidate selection in the next trial may use static data only. Wave data must
not be used to select or tune calibration parameters.
