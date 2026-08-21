# WASS 1.11 fixed-calibration path

Status: `NEEDS_MINIMAL_ADAPTER`

This audit targets the local Windows runtime
`1.11_heads/master-0-g6b82aeb`. The corresponding upstream source was inspected
at commit `6b82aeb`; no WASS source was changed.

## Confirmed path

The official documentation states that `wass_match` and
`wass_autocalibrate` are used only when extrinsic parameters are unknown.
Source inspection confirms the fixed path:

1. configuration contains `intrinsics_00.xml`, `intrinsics_01.xml`,
   `distortion_00.xml`, `distortion_01.xml`, `ext_R.xml`, and `ext_T.xml`;
2. `wass_prepare.cpp` loads R/T from the calibration directory and copies them
   into the frame work directory;
3. `wass_stereo.cpp::load_data` loads work-directory `ext_R.xml` and
   `ext_T.xml` directly;
4. `wass_match` and `wass_autocalibrate` are therefore skipped when fixed
   external calibration is supplied;
5. `wass_stereo` performs the official dense reconstruction unchanged.

Sources: [WASS getting started](https://sites.google.com/unive.it/wass/software/wass/getting-started), [WASS upstream](https://github.com/fbergama/wass), commit `6b82aeb` files
`src/wass_prepare/wass_prepare.cpp`, `src/wass_autocalibrate/wass_autocalibrate.cpp`,
and `src/wass_stereo/wass_stereo.cpp`.

## Conventions and scale

OpenCV stereo calibration defines the supplied transform as

`X_cam1 = R_01 X_cam0 + T_01`.

WASS autocalibration writes its recovered R and T directly to the same files;
the stereo component consumes that direction. The adapter therefore does not
transpose or invert OpenCV R/T. Files are OpenCV XML matrices with nodes
`ext_R` (3x3 double) and `ext_T` (3x1 double). Camera roles are explicit:
cam0=left and cam1=right.

The OpenCV T input and sidecar baseline are metres. However,
`wass_stereo.cpp::load_data` computes the current norm and rescales T to
`env.cam_distance`, which is initialized to 1.0. Thus fixed metric T provides
direction and the known baseline record, but **does not by itself prove that
raw xyzC is metric**. The existing WASS physical-scale recovery remains
mandatory. This behavior is explicit in the adapter sidecar.

## Minimal adapter

`write_wass_fixed_calibration` writes the six OpenCV XML matrices plus a
provenance JSON sidecar. It requires an approved OpenCV quality gate, validates
R/T shapes and rotation geometry, records units and roles, and never invokes
WASS. This is conversion and validation only, not a calibration solver.

The WASS runtime itself supports fixed calibration. Relative to this project's
OpenCV result schema, the requested classification is:

`WASS_FIXED_CALIBRATION_PATH = NEEDS_MINIMAL_ADAPTER`

`AUTOCALIBRATE_REQUIRED_FOR_FIXED_CALIBRATION = FALSE`
