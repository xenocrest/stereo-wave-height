# HomeTank_004 Wave Height Validation

## 1. Purpose and boundary

This validation connects reconstructed metric `XYZ(t)` and signed heights to reusable drift and wave statistics. It is intended for future synchronized industrial stereo systems as well as the present low-cost trial. It does not modify OpenCV `K/D/R/T`, WASS, the static reference, or any raw height product, and it introduces no phone-specific correction.

The wave software chain is `WAVE_PIPELINE_COMPLETED_WITH_STATIC_WARNING`. The scientific classification remains **`WAVE_RESULT_NOT_VALIDATED`** because the static baseline is unstable.

## 2. Data domain

The pipeline currently exports irregular raw `(X,Y,H)` observations rather than a common regular height grid. Wave statistics therefore use the intersection of the five frames' valid physical XY bounding boxes:

- `x = [-0.0959686, -0.0600584] m`;
- `y = [-0.0942312, 0.0059442] m`;
- no interpolation, filtering, point correspondence, or filled grid is used.

The five frames contribute 134,061–165,664 raw observations inside this ROI. The time series is stored in [wave_height_timeseries.csv](wave_height_timeseries.csv).

## 3. Static drift

The static reconstruction used the same fixed calibration and WASS chain. Relative to static frame `000000`, its frame mean Z values give:

| Frame | Mean Z (m) | Signed drift (mm) |
|---|---:|---:|
| 000000 | 0.290724 | 0.000 |
| 000001 | 0.331121 | +40.397 |
| 000002 | 0.233887 | -56.836 |

- maximum absolute drift: **56.836 mm**;
- RMS drift: **40.259 mm**;
- peak-to-peak drift: **97.233 mm**.

The three irregular static clouds have no shared raw observations inside their tiny bounding-box intersection. Consequently, a fixed-ROI spatial difference map, its RMS, P95 and maximum are `NOT_AVAILABLE_NO_COMMON_RAW_SUPPORT`. Producing those values would require a documented grid/association method; none is introduced here. The existing per-frame plane RMS values are 2.01–2.25 mm, showing that locally planar single frames do not imply temporal coordinate stability.

## 4. Wave statistics

Raw signed height is the point-to-static-reference-plane distance. Per-frame spatial means are:

| Frame | Time (s) | Points | H mean (mm) | H RMS (mm) | Peak-to-peak (mm) |
|---|---:|---:|---:|---:|---:|
| 000000 | 20.0 | 141,887 | +22.421 | 22.520 | 15.063 |
| 000001 | 20.1 | 156,062 | -7.072 | 7.369 | 15.190 |
| 000002 | 20.2 | 134,061 | -12.308 | 12.429 | 14.474 |
| 000003 | 20.3 | 154,168 | +0.156 | 1.812 | 14.865 |
| 000004 | 20.4 | 165,664 | -21.109 | 21.230 | 16.871 |

Across all 751,842 ROI observations, raw RMS is **15.314 mm**, the range is **58.712 mm**, and P95 absolute height is **24.106 mm**. The spatial-mean time series has a 43.530 mm peak-to-peak range.

Significant wave height is **`NOT_AVAILABLE`**. The configured five samples cover only 0.4 s and do not provide enough independently identified complete waves for the highest-one-third wave-height definition. No spectral or zero-crossing result is fabricated from this record.

## 5. Analysis-only drift correction

For diagnosis only, each frame is also evaluated after removing its own spatial mean:

$$
H'(x,y,t)=H(x,y,t)-\overline{H}(t).
$$

This leaves a combined RMS of **2.015 mm**, P95 absolute residual of **3.870 mm**, and combined peak-to-peak range of **16.871 mm**. These values describe within-frame spatial structure after removing all spatial-mean motion. They are saved alongside, and never overwrite, raw results. Because a true long-crested or spatially uniform wave can contribute to the removed mean, this is not a corrected wave-height product and cannot be used to claim accuracy.

## 6. Conclusion

The raw time series contains clear temporal variation and millimetre-scale within-frame spatial structure, so a **wave-signal candidate is available**. It is not a validated physical wave signal: the observed 43.530 mm temporal range cannot be separated from the independently measured 97.233 mm static instability, synchronization remains candidate-only, and only five wave frames were processed.

Final classification: **`WAVE_SIGNAL_CANDIDATE_WITH_UNRESOLVED_STATIC_DRIFT` / `WAVE_RESULT_NOT_VALIDATED`**. The method is ready to migrate to a professional synchronized stereo system, where a stable common grid, longer record and independent wave reference can support formal RMS, peak-to-peak and significant-wave-height validation.
