# WASS observability diagnostic patch

This directory records a diagnostic-only patch; it does not vendor WASS source or binaries. Apply `observability.patch` only to upstream commit `6b82aebbf47a692b610fce7e6ea87b6123050c88` in an isolated checkout.

The patch adds read-only export of the pre-cluster depth/valid lattice, computed Z-gap percentile, and an independently enumerated component label map and size table. It does not change configuration, matching, autocalibration, triangulation, percentile selection, production connected-component traversal, filtering, or final export logic.

The first build used OpenCV 4.10.0 while the frozen production executable uses OpenCV 4.6.0. Case 0 and Case 1 `xyzC` hashes did not match. It is therefore `DIAGNOSTIC_BUILD_NOT_NUMERICALLY_EQUIVALENT`; none of its diagnostic values may support scientific conclusions. See `docs/validation/wass_diagnostic_build.md`.
