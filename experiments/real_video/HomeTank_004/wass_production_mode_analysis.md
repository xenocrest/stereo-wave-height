# HomeTank_004 WASS Production Mode Analysis

## 1. Scope and frozen baseline

This analysis defines an engineering execution mode without modifying WASS algorithms, `K/D/R/T`, existing reconstruction results, or acceptance conclusions. The ruler is not used. The measured three-frame baseline is 25.311 s/frame (23.174–29.204 s), and the five-frame diagnostic run occupies 380,287,736 bytes, or 76.058 MB/frame.

## 2. ROI capability audit

The confirmed stereo configuration provides `LEFT_MASK_IMAGE`, `RIGHT_MASK_IMAGE`, and `TRIANG_BBOX_LEFT/RIGHT/TOP/BOTTOM`. These apply in stereo/triangulation. No confirmed unmodified WASS interface applies a physical water ROI to the preceding `wass_match` stage, which is the measured 11.547 s/frame primary bottleneck.

| Mode | Match (s) | Stereo internal (s) | Total (s) | XYZ / plane / height comparison |
|---|---:|---:|---:|---|
| Full image | 11.547 mean | 13.136 mean | 25.311 mean | Existing baseline |
| Water ROI | NOT RUN | NOT RUN | NOT RUN | NOT AVAILABLE |

The water ROI is also not manually registered in both rectified cameras. Cropping source images would change image geometry and require corresponding intrinsic updates, which this task forbids. A downstream mask or triangulation bounding box could reduce retained points and some postprocessing, but calling that a match optimization would be false. Therefore the controlled ROI test stops at `NOT_RUN_UNSUPPORTED_AS_PRE_MATCH_OPTIMIZATION`; no quality numbers are fabricated.

## 3. Diagnostic and production output modes

Diagnostic mode retains extracted frames, rectified/disparity images, WASS workdirs, XYZ, PLY, pixel–XYZ, height samples, logs and reports. Production mode retains measurement-bearing artifacts—compressed height samples, pixel–XYZ correspondence, metric XYZ, CSV/JSON and reports—and marks duplicate PLY plus diagnostic/intermediate data as `PRUNE_AFTER_VERIFIED_CHECKPOINT`. It never deletes raw MP4 files.

Using the existing five-frame run, this policy changes retained data from 380.288 MB to 92.398 MB, a **75.703%** reduction. A separate three-frame serialization measurement reduced XYZ/PLY output time from 0.4931 to 0.2673 s/frame by omitting PLY. The resulting component-sum estimate is 25.085 s/frame versus 25.311 s/frame. This is an output-I/O saving, not a WASS compute speedup, and no files were deleted during this analysis.

## 4. Resumable batches

The generic module supports explicit half-open frame ranges, deterministic gap-free batches, completed-checkpoint registration, and merge of verified `wave_result.json` frame records ordered by `(timestamp_ns, frame_id)`. It rejects duplicate frame IDs and does not infer completion from partial files. The template is [production_mode_template.yaml](../../../configs/wass/production_mode_template.yaml).

## 5. One-hundred-frame preflight

At the measured baseline, 100 frames would require about 2,531.10 s (42.19 min). Existing diagnostic retention projects to 7.606 GB; production retention projects to 1.848 GB. With 64.980 GB free on D: at this check, storage is sufficient.

Execution is nevertheless blocked: the preceding light-event analysis established only a 0.1 s coarse relationship, while frame-level mapping remains `SYNC_NOT_ESTABLISHED`. Running 100 nominal frame-index pairs would violate the explicit prohibition against assuming equal frame indices. Thus zero of 100 frames were run, and XYZ count, plane RMS, height-range and reconstruction-consistency comparisons are `NOT_AVAILABLE_NO_100_FRAME_RUN`.

## 6. Engineering conclusion

Batching and verified artifact retention are portable to professional stereo cameras. The output policy materially reduces retained storage but barely changes WASS computation time. ROI acceleration needs a confirmed geometry-preserving pre-match interface; the currently confirmed downstream masks cannot attack the main `match` bottleneck. Before the controlled 100-frame comparison, establish hardware timestamps/trigger or a validated frame-level time map. No real-time or industrial-performance claim is made.

Machine-readable record: [wass_production_mode_analysis.yaml](wass_production_mode_analysis.yaml).
