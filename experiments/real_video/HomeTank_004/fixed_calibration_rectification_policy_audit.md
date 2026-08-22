# HomeTank_004 Candidate A rectification-policy audit

## Scope and immutable inputs

This is an offline, read-only audit of `FULL_CALIBRATION`. K0/D0/K1/D1/R/T
were read unchanged from `calibration_result.yaml`. No calibration value,
adapter, candidate, WASS binary, source video, or historical result was changed.
WASS and wave data were not run.

The independent calculations used OpenCV 5.0.0, matching the version recorded
for the project calibration result. Image size was 1920x1080. The full matrices
remain in `calibration_result.yaml`; the unchanged translation norm is
0.0686847116 m.

## Independent OpenCV stereoRectify

The calibration-stage policy
`flags=CALIB_ZERO_DISPARITY, alpha=0, D=D_calibration` returned `PASS`:

```text
R1 = [[ 0.9086497895, -0.0879221646,  0.4081975663],
      [ 0.1352406095,  0.9868536297, -0.0884866718],
      [-0.3950513102,  0.1356082833,  0.9085949900]]
R2 = [[ 0.8569418338, -0.1832713342,  0.4817284624],
      [ 0.1246293077,  0.9805905879,  0.1513592896],
      [-0.5001182151, -0.0696686224,  0.8631500762]]
P1 = [[3072.6481016056, 0, -186.3801774979,    0],
      [0, 3072.6481016056, 451.8921585083,     0],
      [0, 0, 1, 0]]
P2 = [[3072.6481016056, 0, -186.3801774979, -211.0439486602],
      [0, 3072.6481016056, 451.8921585083,      0],
      [0, 0, 1, 0]]
Q  = [[1, 0, 0, 186.3801774979],
      [0, 1, 0, -451.8921585083],
      [0, 0, 0, 3072.6481016056],
      [0, 0, 14.5592807617, 0]]
validPixROI1 = [0, 0, 1920, 1079]
validPixROI2 = [0, 0, 1920, 1080]
```

No exception occurred. This reproduces the matrices already stored by the
calibration stage. It is a rectification call pass, not a calibration-quality
pass; `CALIBRATION_QUALITY_FAIL` and `approved_for_wass=false` remain unchanged.

## WASS rectification flow

Source and actual-workdir inspection confirm this path:

1. `wass_prepare` reads D_calibration, undistorts both images, retains the
   recorded K matrices, and saves corrected images;
2. `wass_stereo::load_data` loads those K matrices and ext_R/ext_T, constructs
   camera poses, and normalizes T magnitude to its internal camera distance;
3. because Tx is negative, WASS auto-swaps image/K roles and internally uses
   `R^T,-R^T*T`;
4. WASS calls `cv::stereoRectify` with zero D, flags=0, alpha=1.0 and the
   original image size;
5. it checks the two valid ROIs and emits `the epipole lies inside the image
   plane` when either ROI has zero width/height;
6. remap and crop would follow only for valid ROIs. In this run they were not
   reached successfully; the caller subsequently hit an empty-image assertion.

Sources: WASS commit `6b82aeb`,
[`load_data`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp#L326-L428) and
[`rectify`](https://github.com/fbergama/wass/blob/6b82aeb/src/wass_stereo/wass_stereo.cpp#L434-L595).

The exact WASS policy was independently reproduced after its auto-swap using
K1/K0, zero D, `R^T,-R^T*T`, flags=0 and alpha=1. OpenCV returned normally but
reported:

```text
validPixROI1 = [0, 0, 0, 0]
validPixROI2 = [0, 0, 0, 0]
```

Thus the WASS text is a zero-valid-ROI classification; it is not proof that a
finite epipole lies inside the original raster.

## Epipoles

Using the unchanged project convention `X_cam1=R*X_cam0+T`:

- left epipole, projection of the cam1 center into cam0:
  `(4277.6657, 134.7423) px`;
- right epipole, projection of the cam0 center into cam1:
  `(3786.6227, 28.8087) px`.

Both x coordinates exceed the image interval `[0,1920)`, so both epipoles are
outside the 1920x1080 image. The literal classification
`EPIPOLE_INSIDE_IMAGE=false` applies to both cameras.

## Distortion sensitivity

| Rectification policy | Distortion | ROI1 | ROI2 | API status |
|---|---|---|---|---|
| zero disparity, alpha=0 | calibrated D | `[0,0,1920,1079]` | `[0,0,1920,1080]` | PASS |
| zero disparity, alpha=0 | zero D | `[0,0,1920,1079]` | `[0,0,1920,1080]` | PASS |
| flags=0, alpha=1 | calibrated D | `[0,0,0,0]` | `[0,0,0,0]` | PASS, zero ROI |
| flags=0, alpha=1 | zero D | `[0,0,0,0]` | `[0,0,0,0]` | PASS, zero ROI |
| WASS auto-swap, flags=0, alpha=1 | zero D | `[0,0,0,0]` | `[0,0,0,0]` | PASS, WASS rejects ROI |

Changing only D has no effect on these ROI outcomes. Distortion is therefore
not the controlling cause of this failure, and this offline comparison is not
a Candidate B reconstruction result.

## Classification and next step

The immediate failure classification is
`RECTIFICATION_POLICY_ROI_INCOMPATIBILITY` (choice B: rectification
implementation/policy issue). The poor existing stereo RMS (7.922425 px),
epipolar RMS (9.508413 px), and vertical disparity RMS (21.122547 px) remain
important geometry-quality risks, but they do not explain why alpha=0 yields a
full ROI while alpha=1 yields zero ROI. Distortion sensitivity is negative.

No adapter modification or R/T conversion is required. Candidate B does not
need to be run to diagnose this failure because the D=0 offline policy result
is already identical. If authorized, the next step should be a controlled,
Candidate-A-only rectification-policy compatibility test; it must predeclare
the single policy change and must not use wave data or reinterpret success as a
calibration pass.
