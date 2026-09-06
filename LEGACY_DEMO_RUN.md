# Legacy Presentation Demo Run Guide

This build is `LEGACY_PRESENTATION_ONLY`. It demonstrates the historical software
workflow; its numerical height values are known to be unvalidated.

1. Start `dist\StereoWaveHeightLegacyDemo\StereoWaveHeightLegacyDemo.exe`.
2. Load calibration package
   `D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\calibrations\HomeTank_005_demo_only_v1\manifest.yaml`.
3. If prompted, choose **继续用于演示**.
4. Load LEFT video
   `D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos\wave\HomeTank_005_wave_cam0_LEFT.mp4`.
5. Load RIGHT video
   `D:\research\stereo-wave-height\experiments\real_video\HomeTank_005\videos\wave\HomeTank_005_wave_cam1_RIGHT.mp4`.
6. Wait for the historical common-FOV crop `[0, 272, 522, 722]`.
7. Select the water ROI from `(20, 350)` to `(480, 680)` in full canonical cam1 coordinates.
8. Seek to `9.000 s`, pause, and set the current frame as reference.
9. Seek to `48.000 s`, pause, and run the single-frame measurement.
10. Open the result page to view the height overlay, hover values, point cloud,
    history, and export controls.

The historical run recorded 100% finite ROI coverage but an implausible height
offset of approximately one metre. Do not present those values as physical truth.
