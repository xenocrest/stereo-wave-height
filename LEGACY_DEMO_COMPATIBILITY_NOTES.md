# Legacy Demo Compatibility Notes

This branch restores commit `f54c28a` as an isolated presentation build.

- The executable name is `StereoWaveHeightLegacyDemo.exe`.
- Sessions use `%LOCALAPPDATA%\StereoWaveHeightLegacyDemo\gui_sessions`.
- The window title identifies the classic presentation build.
- Packaging copies this guide and these notes into the distribution.

No calibration mathematics, reference mathematics, WASS parameter, matcher,
height algorithm, surface model, or coordinate transform was changed.

This legacy build is presentation-only. Numerical height values are historical
and are not scientifically validated. Do not use it for physical-accuracy claims.
