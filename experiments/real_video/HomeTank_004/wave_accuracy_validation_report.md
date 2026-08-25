# HomeTank_004 Long-Duration Wave Accuracy Validation

## 1. Input and requested scope

The requested input is the complete HomeTank_004 wave pair using unchanged OpenCV calibration and the existing WASS pipeline:

| Stream | Duration | Frames | Average FPS |
|---|---:|---:|---:|
| cam0 / left | 161.1774 s | 9,556 | 59.2887 |
| cam1 / right | 161.1709 s | 9,670 | 59.9984 |

The intended upper bound is 9,556 timestamp-paired frames. Frame-index pairing is prohibited because the streams have different rates and counts. The existing zero-offset estimate has only medium confidence and is not a validated full-sequence clock mapping.

Pipeline commit at preflight: `1f0b259d8e5cc6e5e8f8c410f5a2775f891ae936`.

## 2. Capacity evidence and execution status

The preceding five-frame real WASS run provides measured—not guessed—resource evidence:

- WASS stereo total per frame: approximately 17.4378 s;
- mean WASS workdir: approximately 44.99 MB/frame;
- complete run output: approximately 76.06 MB/frame.

Linear lower-bound estimates for 9,556 frames are:

- WASS stereo time alone: **46.29 hours**;
- WASS workdirs: **429.92 GB**;
- existing full-output retention pattern: **726.83 GB**.

At preflight, drive D had **65.05 GB (60.59 GiB)** free. Starting the current all-output pipeline would therefore predictably exhaust the drive. The run was not launched and no frame was silently dropped, subsampled or represented as complete.

Status: **`BLOCKED_RESOURCE_AND_SYNCHRONIZATION_PREFLIGHT`**. Completed long-duration frames: **0 / 9,556**.

## 3. Wave and stability results

No long-duration `wave_timeseries.csv` or replacement `wave_result.json` is reported. The existing five-frame files remain the only results and are preserved unchanged. Consequently:

- long-duration success ratio: `NOT_AVAILABLE`;
- height range: `NOT_AVAILABLE`;
- low-frequency drift: `NOT_AVAILABLE`;
- short-period wave variation: `NOT_AVAILABLE`.

The project now includes deterministic gap-free batch planning and capacity preflight. That makes a future run resumable, but it does not solve storage retention or validate synchronization by itself. Deleting intermediates during processing would be a new retention policy and must be designed and approved before execution.

## 4. Independent ruler validation

The ruler remains downstream and independent. [ruler_measurement.yaml](ruler_measurement.yaml) contains no manual observations, so validation status is **`MANUAL_REFERENCE_REQUIRED`**. No automatic ruler reading is inferred.

| Metric | Result |
|---|---:|
| matched manual references | 0 |
| RMSE | `null` |
| MAE | `null` |
| maximum absolute error | `null` |
| mean bias | `null` |

When reference rows are supplied, errors will use $e=H_{reconstruction}-H_{reference}$ without feeding any ruler value back into reconstruction.

## 5. Completion requirements

Before the full-rate run can be executed safely:

1. provide sufficient external storage or approve a documented, recoverable retention policy that preserves required scientific outputs;
2. establish a full-sequence timestamp mapping/tolerance rather than pairing unequal-rate streams by index;
3. choose and record a supervised resumable batch location;
4. optionally provide timestamped manual ruler readings for independent validation.

This report does not claim that long-duration reconstruction or engineering accuracy is complete. It records the precise blockers so the project does not confuse a five-frame demonstration with a 161-second validation.
