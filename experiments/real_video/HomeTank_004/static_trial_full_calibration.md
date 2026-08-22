# HomeTank_004 static trial with full calibration

## Result

`STATIC_GEOMETRY_INVALID`

`static_algorithm_validation_status=FAILED_AT_WASS_RECTIFICATION`

The strict calibration result remains `CALIBRATION_QUALITY_FAIL` and
`approved_for_wass=false`. This trial did not run wave data, Candidate B,
Candidate C, or `wass_autocalibrate`.

## Input and synchronization

Candidate A `FULL_CALIBRATION` used the OpenCV calibration-result K0/D0/K1/D1/R/T
without changing or rescaling T. The corrected manual baseline was not used for
reconstruction. Three static pairs were extracted at cam0 PTS 10.012256,
27.006311, and 44.000511 s. Cam1 used the existing +0.1 s synchronization
candidate and the nearest decoded PTS, producing pair differences 0.088011,
0.094411, and 0.100656 s. Equal frame indices were not used as synchronization
evidence.

## WASS execution

The external runtime was WASS `1.11_heads/master-0-g6b82aeb` at
`D:/wass/dist/bin`. The existing generated matcher and stereo configurations
were used without tuning.

| Stage | Result | Evidence |
|---|---|---|
| prepare | PASS, 3/3 | return codes 0/0/0; fixed calibration loaded |
| match | PASS, 3/3 | return codes 0/0/0; 35/36/28 retained sparse matches |
| autocalibrate | NOT RUN | prohibited by fixed-calibration trial |
| stereo | FAIL, 0/1 | return code -1073740791 at first frame rectification |

`wass_match` writes its diagnostic pose into each workdir. Those files differed
strongly from the frozen calibration and were not allowed to become reconstruction
parameters. Before stereo, the adapter-exported OpenCV ext_R/ext_T were copied
back and verified exactly; T norm remained 0.0686847116 m.

WASS then identified an auto-swapped left/right setup and reported
`the epipole lies inside the image plane`. Rectification yielded no usable image,
after which OpenCV terminated on an empty-input `cvtColor` assertion. The trial
stopped immediately. The remaining two stereo calls were not attempted and no
parameter was tuned.

## XYZ, plane and scale

No `mesh_cam.xyzC` was produced, so the point count is zero. Physical X/Y/Z
ranges, the plane model `z=a*x+b*y+c`, residual RMS/mean/maximum, and water-plane
tilt are unavailable. They are recorded as null rather than inferred.

Scale validation is `FAIL`: there is no XYZ output, and HomeTank_004 records a
visible ruler but no numeric ruler interval or tank dimension suitable for a
quantitative check. Manual baseline, camera height, and pitch were not used to
force or repair the reconstruction.

## Interpretation

The classification is based on the absence of XYZ and a concrete fixed-geometry
rectification failure, not on calibration RMS alone. It does not alter the
historical calibration classification. Candidate A cannot presently close the
static WASS path under the frozen conditions.
