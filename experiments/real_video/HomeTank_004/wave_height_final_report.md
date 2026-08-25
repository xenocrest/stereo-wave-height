# HomeTank_004 Complete Wave Height Output

## 1. Reconstruction status

The configured HomeTank_004 wave run completed five of five timestamp-paired frames through unchanged OpenCV calibration, WASS, XYZ, pixel–XYZ and plane-normal height output. The success ratio is 100% for this configured subset. It covers only 0.4 s and therefore does **not** establish stable long-duration output.

Status: `WAVE_HEIGHT_OUTPUT_COMPLETED_WITH_VALIDATION_WARNING`.

## 2. ROI and per-frame height

The analysis ROI is a metric rectangle in reconstruction XY, selected as the intersection of all five raw-observation bounding boxes. It is applied after WASS and never affects matching or reconstruction:

- origin: `(−0.0959686, −0.0942312) m`;
- width: `0.0359102 m`;
- height: `0.1001754 m`;
- interpolation: none.

Complete machine-readable rows are in [wave_timeseries.csv](wave_timeseries.csv).

| Frame | Valid points | Mean H (mm) | Median H (mm) | RMS H (mm) | P5/P95 (mm) | Min/Max (mm) |
|---|---:|---:|---:|---:|---:|---:|
| 000000 | 141,887 | +22.421 | +22.230 | 22.520 | +19.370 / +26.154 | +16.883 / +31.945 |
| 000001 | 156,062 | −7.072 | −6.968 | 7.369 | −10.410 / −4.047 | −11.562 / +3.628 |
| 000002 | 134,061 | −12.308 | −12.343 | 12.429 | −14.963 / −9.241 | −15.964 / −1.489 |
| 000003 | 154,168 | +0.156 | −0.062 | 1.812 | −2.338 / +3.687 | −4.271 / +10.595 |
| 000004 | 165,664 | −21.109 | −21.267 | 21.230 | −24.315 / −17.197 | −26.767 / −9.896 |

The raw spatial-mean series has RMS **15.164 mm** and peak-to-peak **43.530 mm**.

## 3. Drift analysis

Raw values are preserved. A separate display-only series subtracts a centered three-frame moving mean:

$$
H_{filtered}(t)=H_{raw}(t)-H_{\mathrm{moving\ mean}}(t).
$$

The filtered series has RMS **10.555 mm** and peak-to-peak **25.379 mm**. The window is explicitly marked `DIAGNOSTIC_ONLY_NOT_PHYSICALLY_VALIDATED`: five frames and 0.4 s cannot establish a physical low-frequency cutoff, so this series must not replace raw height or be reported as validated wave motion.

## 4. Independent ruler validation

The ruler is entirely outside reconstruction. [ruler_measurement.yaml](ruler_measurement.yaml) is a separate manual input containing only `frame_id`, `timestamp_ns` and `real_height_mm`. It is not imported by WASS, pixel–XYZ, reference-plane or height modules.

No manual ruler readings are currently registered. Therefore:

- validation status: `MANUAL_REFERENCE_REQUIRED`;
- RMSE: `NOT_AVAILABLE`;
- MAE: `NOT_AVAILABLE`;
- maximum error: `NOT_AVAILABLE`.

Once independent readings exist, the validator computes $e=H_{recon}-H_{real}$ and reports RMSE, MAE and maximum absolute error without changing reconstruction.

## 5. Unified output and conclusion

[wave_result.json](wave_result.json) provides a stable non-GUI interface containing status, timestamps, raw height rows, analysis-only filtered values, aggregate statistics and validation status.

The output workflow is complete for the existing five-frame diagnostic subset and is camera-model independent. HomeTank_004 still has failed static stability, candidate synchronization and no independent ruler values. It proves the result interface, not engineering measurement accuracy. A professional synchronized stereo run can use the same configuration, CSV and JSON contracts with a longer sequence and independent reference.
