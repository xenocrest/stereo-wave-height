# HomeTank_004 On-demand Single-frame Backend Validation

## Purpose and architecture

The new backend expresses the final product boundary:

```text
explicit synchronized image pair
or left/right video + user target time + validated clock mapping
  → canonical selected pair
  → existing fixed-calibration ReconstructionPipeline
  → WASS prepare/match/stereo (never autocalibrate)
  → XYZ → pixel–XYZ → plane-normal H(x,y)
  → GUI-facing JSON and Markdown
```

It reuses the existing OpenCV calibration loader and equality check, WASS runner, xyzC loader, surface extraction, height calculation, pixel–XYZ projection and report artifacts. No phone model is referenced in backend code. Mode A accepts an explicitly synchronized image pair. Mode B accepts two videos and target time `t` and must pass the PTS-based synchronization gate before images or WASS are invoked.

## Time model and gate

The model is

$$
t_R = a t_L + b.
$$

For a selected decoded left PTS $t_{L,a}$, the nearest decoded right PTS $t_{R,a}$ is evaluated with

$$
e_t=t_{R,a}-(a t_{L,a}+b).
$$

The local frame period is the smaller of the two videos' median decoded PTS intervals. `FRAME_PAIR_SYNC_ESTABLISHED` requires a validated frame-level model and $|e_t|$ no greater than half that period. Half-to-one period is a warning. A coarse-only model always returns `FRAME_LEVEL_SYNC_NOT_ESTABLISHED`, even when one nearest-PTS residual is small.

## HomeTank_004 result

The static candidate at 10.012256 s has no validated frame-level clock model for the static videos and was stopped without extracting a pair. For the wave candidate at 20.0 s, the existing coarse light-event model has `a=1`, `b=0`, ten events and 0.054772 s fit residual RMS. Decoded PTS diagnostics were:

| Item | Value |
|---|---:|
| Requested left time | 20.000000 s |
| Actual left PTS | 20.001878 s (`pts_1800169`) |
| Actual right PTS | 20.000533 s (`pts_1800048`) |
| Pair residual | -1.345 ms |
| Local frame period | 16.656 ms |
| Gate | `FRAME_LEVEL_SYNC_NOT_ESTABLISHED` |

The residual alone lies within half a local frame period, but the underlying mapping still has only 10 Hz event evidence and explicitly records `frame_level_established=false`. Treating this coincidence as synchronization would violate the project gate. No selected stereo pair was accepted, and WASS, XYZ, pixel–XYZ, reference plane, height and plane RMS are all `NOT_RUN/NOT_AVAILABLE`. The external small blocked-result JSON is stored outside Git; no video or WASS artifact was committed.

## Result and validation boundary

Final classification: `FRAME_LEVEL_SYNC_NOT_ESTABLISHED`. This is correct backend behavior, not pipeline closure. A future professional system should supply hardware-trigger timestamps or another validated frame-level mapping. Once that requirement is met, the same request enters the mature fixed-calibration pipeline without redesign.

Ruler validation remains strictly downstream: reconstruction code imports no ruler module or reference file. Ruler data does not participate in synchronization, WASS, XYZ, reference-plane construction or height calculation.
