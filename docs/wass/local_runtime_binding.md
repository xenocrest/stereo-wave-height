# Local WASS Runtime Binding

Inspection date: 2026-08-11

## Located environment

An existing native Windows WASS installation was found at
`D:\wass\dist\bin`. It is not on Windows `PATH`; the executables must be called
by absolute path or through the project runtime binding. WSL has no registered
distribution on this host, and Docker CLI/runtime was not found. No installation
or compilation was performed.

All four binaries launch and print this observed banner before rejecting the
unsupported `--help` argument:

```text
v. 1.11_heads/master-0-g6b82aeb
[Release] Windows-10.0.19044 - MSVC, OpenCV 4.6.0
```

The embedded short commit is `6b82aeb`; the source snapshot at `D:\wass` has no
`.git` metadata, so a full commit SHA/tag cannot be confirmed locally. This
runtime is different from the project's reproducibility baseline WASS `v_1.5`
commit `59f1b1c...`. It is bound as an observed local runtime, not relabelled as
the locked baseline.

| Stage | Path | SHA-256 | Callable |
|---|---|---|---|
| prepare | `D:\wass\dist\bin\wass_prepare.exe` | `81CD7085B17127C2EA96D0F1BC7CFACF1DC63D8B683E28FAB859E1DCF036F06B` | yes |
| match | `D:\wass\dist\bin\wass_match.exe` | `69D5DB33E9400A741DB34D6104EC2B34C23459DFE842373F5BD0A37144607B47` | yes |
| autocalibrate | `D:\wass\dist\bin\wass_autocalibrate.exe` | `B869AF7B32E5BD0691989E0CF760A7554BC18669DCC42CA62837C987907C1FA3` | yes |
| stereo | `D:\wass\dist\bin\wass_stereo.exe` | `BDE66000C54940104A3978C68C9C3FEA3BAE00B43410F0B6B032407A690B57B9` | yes |

OpenCV 4.6 DLLs are colocated with the executables. The previous Windows driver
script declares no extra environment variables (`ENV_SET=''`). No project code
adds the runtime directory to global `PATH`.

`wassgridsurface` was not found in the active `D:\python` environment, the
searched user/D-drive locations, or as a command. Its installed version and
path remain **UNKNOWN/TODO**.

## Project binding

The machine-observed example is
`configs/wass/local_runtime.windows.example.json`. Core code contains no
personal path defaults. `WassRuntimeBinding` also accepts explicit `wsl` and
`docker` bindings through a caller-supplied `command_prefix`; it never invents
a distribution, image, mount, or executable path.

The current native binding can be checked without running a reconstruction:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
python -c "from adapters.wass.runtime import load_runtime_binding,probe_core_runtime; b=load_runtime_binding('configs/wass/local_runtime.windows.example.json'); print([(r.stage,r.callable,r.returncode) for r in probe_core_runtime(b)])"
```

For this build a non-zero result from `--help` is expected because the option is
not supported. A stage is callable only if process creation succeeds and its own
`wass_<stage>` banner is captured. Real pipeline runs retain strict zero-return
requirements.

## Previous successful run evidence

Existing data remains outside this repository:

- input/config root: `D:\WASS_DATA`;
- paired images: `images\cam0` and `images\cam1`, 50 JPEG pairs;
- completed work directory: `D:\WASS_DATA\work`;
- shell history: Windows PowerShell PSReadLine history, lines recording prepare,
  match, config generation, and stereo commands;
- driver script: `D:\wass\matlab\run_wass.m`.

The old `wass_stereo_log.txt` records successful loading of 2456 x 2058 images,
dense stereo, 2,761,170 triangulated points, a largest component of 2,538,928
points, plane fitting, and successful compressed point-cloud output. This is
evidence that the located runtime previously completed core reconstruction; it
is not copied into Git and is not reused as validation truth.

## Confirmed input/config formats

The old run confirms:

- paired JPEG names such as
  `000000_0000000000000_01.jpg` / `000000_0000000000000_02.jpg`;
- `wass_prepare --workdir <dir> --calibdir <dir> --c0 <left> --c1 <right>`;
- OpenCV XML root `<opencv_storage>`;
- matrix node name `intrinsics_penne` for both 3 x 3 intrinsics and 5 x 1
  distortion vectors, with `type_id="opencv-matrix"` and `dt=d`;
- generated text configs use commented `KEY=value` defaults;
- `wass_match <matcher_config.txt> <workdir>`;
- `wass_autocalibrate <workspaces.txt>` in the existing MATLAB driver;
- `wass_stereo <stereo_config.txt> <workdir>`.

The previous PowerShell history directly records prepare, match, and stereo.
Autocalibrate invocation is confirmed by the existing driver and a callable
binary, but successful execution in that specific single-workdir manual session
is **UNKNOWN**.

## Confirmed output formats

The completed work directory confirms actual filenames including
`undistorted/00000000.png`, `matches.txt`, `matcher_stats.csv`, `ext_R.xml`,
`ext_T.xml`, camera poses, projection matrices, disparity diagnostics,
`plane.txt`, `scale.txt`, `wass_stereo_log.txt`, and `mesh_cam.xyzC`.

Confirmed schemas:

- `matcher_stats.csv` is semicolon-delimited with match count plus average,
  standard deviation, minimum, and maximum epipolar error;
- `plane.txt` contains four newline-separated floating-point coefficients;
- the existing `run_wass.m` reads every frame's `plane.txt`, transposes each
  four-value vector to one row, and writes the rows to root `planes.txt`;
- `mesh_cam.xyzC`, according to the colocated `load_camera_mesh.m`, contains a
  `uint32` point count, six `double` limits, a 3 x 3 `double` inverse rotation,
  three `double` inverse-translation values, then a 3 x N `uint16` payload. The
  loader dequantizes by component using the limits, then applies the inverse
  rigid transform.

The physical unit of the resulting mesh remains **UNKNOWN/TODO**. The old
`baseline.txt` value `3.0`, `scale.txt` value about `0.299674`, and mesh numeric
ranges are observations, not sufficient proof of metre/mm/normalized units.

No `gridded.nc` was found, so its real local schema, mask polarity, dimension
order, units, and relationship to the absent local `wassgridsurface` remain
**UNKNOWN/TODO**.

## Read-only boundary and next gate

No file under `D:\wass` or `D:\WASS_DATA` was modified or copied into the
project. The runtime/config paths are external inputs. The Case 0 environment
blocker for the four core stages is removed. Before Case 0, the remaining gate
is to create simulation-specific OpenCV XML and configs deliberately, without
reusing old experimental calibration as if it belonged to the virtual cameras.
