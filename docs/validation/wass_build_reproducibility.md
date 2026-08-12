# WASS build reproducibility audit

Audit date: 2026-08-12

## Decision

Status: **BUILD_ENVIRONMENT_NOT_REPRODUCED**.

The required clean upstream rebuild was not performed. The production architecture, configuration, OpenCV runtime binaries, and compiler generation were identified, but the exact toolchain and original modular OpenCV 4.6 development tree were not recovered. No clean or patched equivalence hashes exist, and diagnostic exports remain disabled.

## Production audit

| Property | Confirmed value | Evidence |
|---|---|---|
| WASS source | `6b82aebbf47a692b610fce7e6ea87b6123050c88` | version string/upstream commit |
| architecture | x64 (`PE machine 8664`) | PE headers |
| configuration | Release | banner and `IsDebug=false` |
| linker | 14.28 | PE headers |
| likely toolset | VS 2019/v142 | inference from linker; exact compiler is **UNKNOWN** |
| CRT | dynamic MSVC/UCRT | PE imports |
| iterator debug level | 0 | packaged `wass_lib.lib` directives |
| packaged library marker | `_MSC_VER=1900`, `/MD` | `wass_lib.lib` directives; indicates a prebuilt/mixed artifact |
| OpenCV | custom modular 4.6.0 Release x64 | imports, versions, PE metadata |
| embedded OpenCV path | `D:\dev\lib\opencv-4.6.0\build\bin\Release` | DLL RSDS/PDB record |
| CMake/options/optimization/SIMD/FP flags | **UNKNOWN** | cache, projects and logs absent |

The official OpenCV 4.6 GitHub Windows package was inspected outside Git. It provides `opencv_world460.dll`, whereas production uses modular DLLs, so it is not the production development package.

## Frozen OpenCV hashes

| DLL | SHA-256 |
|---|---|
| `opencv_calib3d460.dll` | `C3A72881AE10EAA03FE2B876239986BABC7BBE8BCAD937D4B1D7319F42F2C3EC` |
| `opencv_core460.dll` | `EE6C31174808A8796CBD0D505BBCB7B77F3187FCC99C00578A1811A8338A15CB` |
| `opencv_features2d460.dll` | `0D35DF30F5AD0E79077DF5C52107A4070E14880F0B29AA18820401B337BF7074` |
| `opencv_flann460.dll` | `9B5BF8EFDBC933A358654C56FECCE3DCEEAA12775A168654D5896416F041CE19` |
| `opencv_highgui460.dll` | `26ED2E834506219483F59106FDD44AD0D927CDCAC8BF49996101B3EC87D46B58` |
| `opencv_imgcodecs460.dll` | `92BDAC754FD40C9ADF278A0FD7EF5DDDE0406F7DDAF9ADB28F95BC6696BE978B` |
| `opencv_imgproc460.dll` | `98BAAF1F8B94D6B913A3BE1693D307F2A307BBF913DE0DE65A4B6B444530DE4D` |
| `opencv_videoio460.dll` | `551015A15B69CBDBD2D3B9CC5DBA1C4A7FADCCE0474D112D428498DDFDC5D003` |

`wass_stereo.exe` directly imports calib3d, highgui, imgcodecs, imgproc, and core. The remaining DLLs are packaged but not direct imports.

## Other dependencies

- Boost version: **UNKNOWN**; it is statically linked and production provenance is absent.
- Eigen is not a required linked dependency for `wass_stereo`.
- SBA, LAPACK, BLAS, and f2c are dependencies of `wass_autocalibrate`, not the isolated `wass_stereo` target.
- Production Windows SDK and CMake versions: **UNKNOWN**.

## Recovery attempt

1. Official OpenCV 4.6 was downloaded and inspected outside Git; its monolithic layout differs from production.
2. Frozen DLL exports can generate import libraries, but this does not recover exact headers, compile flags, or ABI provenance.
3. VS 2019 Build Tools announced MSVC `14.29.30133`, but installer state remained `installed:false` and no callable `cl.exe` appeared. It was not accepted as recovered.
4. Even 14.29 would differ from the production PE linker 14.28; the exact MSVC minor version remains unresolved.

No production executable, WASS algorithm, configuration, or result was changed.

## Equivalence outcome

| Comparison | Case 0 xyzC | Case 1 xyzC | Level |
|---|---|---|---|
| official vs clean upstream | NOT RUN | NOT RUN | none |
| official vs patched diagnostic | NOT RUN | NOT RUN | none |

The clean gate precedes patching. Since the clean environment was not reproduced, the observability patch was not rebuilt and the prior OpenCV 4.10 data remain invalid. Level B/C were not substituted for Level A.

## Required recovery

Recover the original OpenCV development tree/cache from `D:\dev\lib\opencv-4.6.0\build`, or an archived manifest containing headers, import libraries, CMake cache and flags. Install a callable v142 toolchain and determine whether MSVC 14.28 can be restored. Build clean `6b82aeb` first; only byte-identical Case 0 and Case 1 `mesh_cam.xyzC` permit a patched build.

Until Level A passes, status remains `OBSERVABILITY_LIMITATION` and Case 2 remains prohibited.
