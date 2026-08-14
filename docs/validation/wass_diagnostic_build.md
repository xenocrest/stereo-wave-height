# Isolated WASS diagnostic build

## Decision

Status: **DIAGNOSTIC_BUILD_NOT_NUMERICALLY_EQUIVALENT**.

Follow-up audit status: **BUILD_ENVIRONMENT_NOT_REPRODUCED**. Production uses a v142-era 14.28 linker and a custom modular OpenCV 4.6 build, but the exact compiler and development tree were not recovered. Clean and patched builds were therefore not rerun. See [wass_build_reproducibility.md](wass_build_reproducibility.md).

An isolated diagnostic tree was established at `D:\wass_diagnostic` from exact upstream commit `6b82aebbf47a692b610fce7e6ea87b6123050c88`. Production executables under `D:\wass\dist\bin` were not changed. Source, builds, binaries, copied workdirs, and generated arrays remain outside Git.

The diagnostic executable built successfully, but both mandatory `mesh_cam.xyzC` comparisons failed. Its generated diagnostic arrays are quarantined and are not reported as measurements.

## Frozen baseline

| Artifact | SHA-256 |
|---|---|
| production `wass_stereo.exe` | `BDE66000C54940104A3978C68C9C3FEA3BAE00B43410F0B6B032407A690B57B9` |
| production `wass_prepare.exe` | `81CD7085B17127C2EA96D0F1BC7CFACF1DC63D8B683E28FAB859E1DCF036F06B` |
| production `wass_match.exe` | `69D5DB33E9400A741DB34D6104EC2B34C23459DFE842373F5BD0A37144607B47` |
| production `wass_autocalibrate.exe` | `B869AF7B32E5BD0691989E0CF760A7554BC18669DCC42CA62837C987907C1FA3` |
| `stereo_config.txt` | `79CA52BCDE7612C25A40C62412411DDDB679CA8D0DEA056CD3DC5BD46F14D843` |
| `matcher_config.txt` | `BAE1E60A3680BC0193628C35BFFB7FD68BA5E8C672F12A489284BD25B25EAF32` |

Input data remain outside Git at `D:\stereo-wave-height-runs\case1-constant-20260811`. Static image hashes are left `5700D4CE03602E993AD7517B74C67CBA7BE677DD9523E971AB1AD38BEB82D877` and right `147305A39455A511AD6E394D06A48331E2CA85B0202B479C820D3FF3A16E3CE1`. Raised image hashes are left `7127EAA0857F8216BB317BFBC859630A7F8C26EF18BE4FC5653A13A7F481F78A` and right `D3708E9FEDAD64AC12C96D9295F0EE1A9FFCB0E744A3F487C667AB28BA9DE9EB`.

## Diagnostic-only outputs

The complete patch is `external/WASS/diagnostics/observability.patch`. It adds:

- `precluster_depth.bin`: magic `WASSPCZ1`, little-endian `uint32` width/height, row-major `double Z`, then row-major `uint8 valid`;
- `zgap_threshold.txt`: percentile, gap count, zero-based index, and double threshold;
- `component_labels.bin`: magic `WASSCCL1`, dimensions, row-major signed `int32` labels (`-1` invalid);
- `component_sizes.csv`: component ID and point count;
- `retained_component_id.txt`: largest-component label.

Full enumeration uses separate vectors and the same four-neighbor strict `abs(delta Z) < tau` predicate. It never writes `Point.valid`, `Point.visited`, `Point.component_id`, or `Point.p3d`. The original production cluster still selects and extracts the final mesh. No parameter or numerical algorithm was changed.

## Build provenance

- WASS source: official commit `6b82aeb...`;
- `incfg`: `a983b1b1c6100316790afc91dffef77a4ebbe424`;
- MSVC 19.44.35228, Release, x64;
- diagnostic OpenCV 4.10.0; production OpenCV 4.6.0;
- diagnostic Boost 1.82.0;
- diagnostic executable SHA-256: `A57F128D7BD545E94540A2925C70554B3C95B2C706D72EDE61F168FAAA0A7C22`.

The OpenCV mismatch is a confirmed build-environment difference and sufficient to reject equivalence. It does not alone prove the exact cause of every output difference.

## Equivalence gate

| Frame | Role | production xyzC | diagnostic xyzC | production triangulated / retained | diagnostic triangulated / retained | Result |
|---|---|---|---|---:|---:|---|
| `000000` | static | `4563C828645022E468C838A7B6EBA3D311E348DD71FF0D809D391845BB7E6DE1` | `C09B427F3A47E118A9DEEF6C0EDADA063B87C4AEA51E011D6BEE8BA762A5CC65` | 4,322,503 / 4,311,954 | 4,318,338 / 4,307,929 | FAIL |
| `000002` | +10 mm | `07774135E774ABF192B538BCC8D49F40A7E7A183C817B9880958EFD0C3508C5C` | `E152C735352828F2137B1A4A5CBE8CC61FC98B2F1A16D8134D6EDF93764D7477` | 4,331,598 / 1,794,468 | 4,327,429 / 1,793,477 | FAIL |

Consequently Static/Case 1 tau, Z-gap distributions, complete component sizes, and strip alignment remain **UNKNOWN**. Values emitted by the rejected build must not be cited.

## Recovery

重建正式运行工具链，尤其是 OpenCV 4.6.0 及兼容的编译器和依赖；随后在隔离环境重新构建并重复冻结的 Case 0/1 门控。只有在 `mesh_cam.xyzC` 字节一致，且平面、姿态、尺度、诊断图、数值日志和点数均等价后，诊断数组才可使用。

## Upstream issue draft

> WASS exposes the final largest-component mesh and a lossy component image, but not the pre-cluster depth/valid lattice, selected numeric Z-gap threshold, or lossless component labels/sizes. These are needed to diagnose fragmentation without changing matching, triangulation, filtering, percentile selection, or connectivity. Would the project consider optional diagnostic-only export of row-major double Z plus validity, percentile metadata (`r`, gap count, index, threshold), and lossless int32 labels/size table, with default behavior and all algorithms unchanged?

Draft only; no upstream issue was submitted.
