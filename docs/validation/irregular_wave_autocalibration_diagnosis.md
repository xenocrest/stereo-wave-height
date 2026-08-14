# IRR-1 WASS 自动标定诊断

Status: **IRR-1 FAIL PRESERVED; IRR-1A SUBSET ADAPTATION PASS**

## 官方与本地接口事实

The native CLI accepts exactly one work-directory list. Source
`wass_autocalibrate.cpp` loads every existing directory in that list and only
their `matches_epionly.txt`. On success it writes one common `ext_R.xml`,
`ext_T.xml` and `H.xml` to each listed workdir. `wass_stereo.cpp` then reads
those three per-workdir files independently.

The official/local MATLAB driver defines `MAX_FRAMES_TO_MATCH=50` with the
comment “generally no need to change this”, selects a subset when the sequence
is larger, runs autocalibrate, and runs stereo per frame. The source-backed
interface therefore supports calibration from selected matched frames, but the
driver does not itself copy successful calibration to unmatched prepared
workdirs. Explicitly distributing the same official output files supplies the
per-frame interface that stereo requires; no numerical algorithm is changed.

The terminal text `SBA failed` is misleading here. The actual source condition is
strictly `post_SBA_mean_epipolar_error < pre_SBA_mean_epipolar_error`. The
homography determinant is logged but not tested. IRR-1 failed because pre and
post values were equal at displayed precision, not because determinant 0.999967
violated a threshold.

## 预注册子集矩阵

Dynamic IDs are produced by `round(linspace(2,51,N))`, require exact uniqueness,
and include both endpoints. No result-dependent replacement is permitted.

| run | composition | matches | pre / post mean epi error (px) | result |
|---|---|---:|---:|---|
| AC-04 | 2,18,35,51 | 6,979 | 2.86193e-6 / 2.87839e-6 | FAIL |
| AC-06 | 2,12,22,31,41,51 | 10,613 | 1.33286e-4 / 4.93377e-6 | PASS |
| AC-10D | 2,7,13,18,24,29,35,40,46,51 | 17,722 | 0.257261 / 6.26708e-6 | PASS |
| AC-20 | deterministic 20 dynamic | 36,393 | 5.30737e-6 / 5.30737e-6 | FAIL |
| AC-30 | deterministic 30 dynamic | 54,304 | 5.12477e-6 / 5.12480e-6 | FAIL |
| AC-40 | deterministic 40 dynamic | 72,203 | 3.29128e-4 / 5.94683e-6 | PASS |
| AC-50D | all 50 dynamic | 90,537 | 1.79617e-4 / 5.84310e-6 | PASS |
| AC-52 | 2 static + all 50 dynamic | 95,083 | 5.11451e-6 / 5.11451e-6 | FAIL |
| AC-10DS | same AC-10D + 2 static | 22,268 | 4.54307e-6 / 4.54568e-6 | FAIL |

AC-10 and AC-50 are aliases of AC-10D and AC-50D. Successful runs produced
different calibration hashes, expected because they use different match sets;
the exact hashes are retained in the compact JSON evidence.

There is no monotonic frame-count boundary: largest passing N is 50 dynamic;
smallest failing N is 4 dynamic. The outcome follows whether SBA strictly
improves the already tiny initial error, not a maximum input count.

## 静水帧与时间区域效应

AC-10D passes while the identical dynamic subset plus the two duplicate static
frames (AC-10DS) fails. AC-50D passes while AC-52 fails. Thus static inclusion
has a repeatable effect in these two controlled comparisons.

At N=10, full-window and early-window subsets pass, while the late-window subset
fails (`5.23102e-6 -> 5.23131e-6`). This is evidence of match-combination/time-
region conditioning, not proof that an individual late frame is defective. No
unbounded frame search was performed.

## IRR-1A 选择与未参与标定帧验证

AC-10D was frozen before height reconstruction because it spans the entire
0--9.8 s window, provides ten multi-frame constraints, has modest cost, and does
not use static duplicates or truth/error results. It was not selected for the
best final RMSE. Its calibration hashes are:

- R: `ad5ea4cec04b9070ce954c0b726f81da27e154342639fe3bb1e49ba5e4d76731`
- T: `a9631686ac29cd9987704ebff0ea4d37a3cbbd20dcc66922ad4be7dd44e50a79`
- H: `7cd0a00250c35ffec8f6ba8214efc908bed45861e6ea207a5c34765d102bdf32`

The unchanged calibration was distributed to all 52 workdirs. Stereo returned
zero for static frame 0, subset frame 2, unseen middle frame 27, subset frame 29
and last frame 51, then for all 52 frames. This validates both subset and unseen
use through the official per-workdir interface.

## 结论与未知项/待办

IRR-1's original joint 52-frame autocalibration remains permanently FAIL.
IRR-1A is a new adaptation and completes the unchanged stereo/grid/height chain.
No WASS parameter, threshold, source, image, truth or acceptance gate changed.

The exact reason particular deterministic match combinations begin with a
near-perfect essential matrix while others do not is `UNKNOWN/TODO`; resolving
that would require a separate match-conditioning study. It is not required to
claim a frame-count limit, because the matrix disproves such a limit.
