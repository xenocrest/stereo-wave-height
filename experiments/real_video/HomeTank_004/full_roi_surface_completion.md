# HomeTank_004 full-ROI surface completion experiment

## Scope and boundary

This experiment asks whether frozen WASS observations can support a continuous height estimate over a large user-selected water ROI. It ran no WASS process and changed no calibration, synchronization, WASS parameter, height definition, local MLS policy, ruler data, or frozen artifact.

The result is an internal WASS-surface consistency and engineering feasibility test. It is not independent physical validation and cannot correct the known absolute-height offset.

## Global model

The formal experimental model is SciPy `RBFInterpolator` with a thin-plate-spline kernel in physical reference-plane coordinates `(X,Y)` measured in metres. A scattered smoothing B-spline was tried first as prescribed, but FITPACK reported unstable fitting for the irregular support and produced zero/exploding extrapolation; it was rejected and is not retained as a product path.

Only finite frozen WASS `(X,Y,H)` observations enter the model. A conservative `median ± 8 MAD` filter removes extreme height outliers. Deterministic physical-XY cells contribute median control points, limiting each fit to approximately 1,000–1,500 controls. Ruler measurements, manual clicks, GUI ROI geometry, and previous estimates never enter fitting truth.

The smoothing noise scale is `1 mm`, derived from the committed frozen local hold-out RMSE range of approximately `0.43–1.06 mm`. There was no parameter grid search.

## Observed-domain global hold-out

Each fit excludes up to 500 deterministically selected observations with seed `20260831`.

| Dataset | Raw | Filtered | Controls | MAE | RMSE | P95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Static R0 | 166,479 | 162,726 | 1,469 | 0.808 mm | 1.383 mm | 2.872 mm | 9.747 mm |
| Wave Case 1 | 86,316 | 86,039 | 1,252 | 0.784 mm | 1.271 mm | 2.106 mm | 7.498 mm |
| Wave Case 2 | 34,955 | 33,940 | 1,227 | 0.360 mm | 0.828 mm | 1.198 mm | 10.191 mm |

Coverage is 100% for all three hold-outs. Therefore the model passes a limited `GLOBAL_SURFACE_COMPLETION_SANITY_PASS_IN_OBSERVED_DOMAIN`: it reproduces held-out samples within the region already physically supported by WASS.

## Large-ROI smoke

No newer saved large GUI ROI could be recovered: the latest completed saved measurement still predates interactive ROI selection. For the required feasibility smoke, the selected cam1 image was inspected and a large water-query rectangle `(120,190)–(1500,900)` was used. The rectangle contains 981,891 pixels and is only a query domain, never fitting truth.

| Source status | Count | Fraction |
|---|---:|---:|
| OBSERVED | 5,495 | 0.560% |
| ESTIMATED_LOCAL | 0 | 0.000% |
| ESTIMATED_GLOBAL | 478,744 | 48.757% |
| UNSUPPORTED | 497,652 | 50.683% |

Total valid coverage is only `49.317%`, far below the requested `>99%` target. Generation took `36.137 s`, also exceeding the `<10 s` goal. The resulting range was `-103.177…508.741 mm` (mean `56.163 mm`, median `65.190 mm`), which is grossly inconsistent with the fitted observed water-height distribution and shows extrapolation spikes/divergence.

## Decision

The observed-domain hold-out does not validate large-domain extrapolation. The current WASS observations occupy only a small physical surface region; a global smooth model cannot truthfully infer an arbitrarily larger user ROI merely because those pixels are visible in the image. Forcing values would disguise unsupported extrapolation as measurement.

Final classification: `GLOBAL_SURFACE_COMPLETION_UNSTABLE`.

Per the task's stop condition, the experimental model is not connected to the formal dense pipeline or GUI. The four-state GUI, full-ROI product output, README update, and packaged EXE rebuild are intentionally not performed. Existing `OBSERVED / ESTIMATED / UNSUPPORTED` artifacts remain unchanged and compatible.

The next defensible step is not a larger completion radius. It is to establish physical WASS support over the intended ROI (improved calibration/texture/acquisition geometry) or formally restrict the selectable ROI to a validated physical support domain before reconsidering global completion.

