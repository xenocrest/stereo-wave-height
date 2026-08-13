# Pre-purchase validation matrix

This table is the long-term summary of pre-purchase simulation evidence. A dash
means the metric does not apply or was not reported under that test's protocol.
Case 2/G0 values below use the corrected explicit world/grid alignment.

| ID | test type | A / height | lambda | f | B / Z | spatial / temporal samples | raw support | min component retention | bias | RMSE | MAE | max | wave errors (A; lambda; f; phase) | result | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| Geometry | ideal stereo geometry | variable | - | - | 0.20 / variable m | analytical | - | - | - | machine precision | - | - | - | PASS | Projection/triangulation unit validation only |
| Case 0 | static plane | 0 | - | - | 0.20 / 2.00 m | 160 grid | 100% | 99.756% | ~0 | diagnostic zero field | ~0 | ~0 | - | PASS | ideal static closure |
| Case 1 | constant offset | +10 mm | - | - | 0.20 / 2.00 m | 160 grid | 100% | 99.890% | about -1 mm | about 1.03 mm | about 1.12 mm | about 6.63 mm | - | PASS | frozen ZGAP=99.5 repeatability result; see dedicated report |
| Case 2/G0 | sinusoid baseline | 10 mm | 0.80 m | 0.50 Hz | 0.20 / 2.00 m | 80 / 10 | 100% | 99.9409% | -0.258 mm | 0.859 mm | 0.691 mm | 2.509 mm | -0.306 mm; <1e-12 m; 0 Hz; +0.000207 rad | PASS | kinematic synthetic wave |
| G1 | amplitude only | 30 mm | 0.80 m | 0.50 Hz | 0.20 / 2.00 m | 80 / 10 | 100% | 99.8449% | -0.433 mm | 1.030 mm | 0.849 mm | 3.398 mm | -0.404 mm; <1e-12 m; 0 Hz; +0.000406 rad | PASS | amplitude factor only |
| G2 | frequency only | 10 mm | 0.80 m | 1.00 Hz | 0.20 / 2.00 m | 80 / 5 | 100% | 99.9625% | -0.109 mm | 0.739 mm | 0.604 mm | 2.099 mm | -0.311 mm; <1e-12 m; 0 Hz; -0.002633 rad | PASS | frequency factor only; low temporal margin |
| G3 | combined stress | 30 mm | 0.80 m | 1.00 Hz | 0.20 / 2.00 m | 80 / 5 | 100% | 99.8593% | -0.545 mm | 1.131 mm | 0.925 mm | 3.672 mm | -0.341 mm; <1e-12 m; 0 Hz; -0.003247 rad | PASS | tested amplitude-frequency combination |
| IRR-1 | deterministic 3-component irregular wave | -27.981 to +20.635 mm evaluated | 0.80/0.50/1.20 m | 0.50/0.80/0.30 Hz | 0.20 / 2.00 m | min 50 / min 6.25 | N/A | N/A | N/A | N/A | N/A | N/A | point RMSE N/A | FAIL/BLOCKED | prepare/match pass; repeatable post-SBA autocalibration failure; stereo/grid not run |

The frozen regular-wave gates are height RMSE/MAE <=10 mm, maximum absolute
error <=30 mm, raw support >=95%, and hole rate <=5%. Wave-parameter errors are
reported but are not retrospectively assigned acceptance thresholds.
