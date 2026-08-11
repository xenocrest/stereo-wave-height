# wassgridsurface 0.11.4 integration

## Provenance and scope

The gridder is the official WASS companion package maintained by Filippo
Bergamasco and published on PyPI as `wassgridsurface==0.11.4` under GPL-3.0.
The audited wheel has SHA-256
`eebf61ee2a4ff59db96f648d5378be50c87c63df65af8f943b44e6dae4322732`.
It was installed outside Git at
`D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv`. No WASS or gridder
source was modified.

Primary sources:

- [PyPI 0.11.4 release and usage](https://pypi.org/project/wassgridsurface/0.11.4/)
- installed 0.11.4 wheel `METADATA`, `wassgridsurface.py`,
  `netcdfoutput.py`, and `wass_utils.py`;
- WASS `D:\wass\matlab\run_wass.m` for historical `planes.txt` aggregation;
- actual Case 0 `gridded.nc`, SHA-256
  `47ae2dc4de384d4be081d507bbb139ca8382ca6f2f8c518ce32b809524c27f46`.

Large run products remain outside the repository under
`D:\stereo-wave-height-runs\case0-static-20260811`.

## Official data chain

```text
per-frame *_wd/mesh_cam.xyzC
per-frame *_wd/plane.txt
camera matrices and undistorted image in first *_wd
  -> root planes.txt
  -> wassgridsurface setup + baseline
  -> config.mat and area_grid.png
  -> wassgridsurface DCT grid
  -> gridded.nc
```

`run_wass.m` reads each four-value `plane.txt`, transposes it into one row, and
writes all rows to root `planes.txt`. Version 0.11.4 loads that matrix and uses
the column-wise NaN-aware mean plane. It aligns every `xyzC` cloud to that plane,
inverts Z, and multiplies coordinates by the supplied camera baseline.

## Case 0 configuration

The input truth domain is x `[-0.9,0.9] m`, y `[-0.8,0.8] m`. The reconstructed
plane-aligned footprint is approximately x `[-1.053,0.852] m`, y
`[-0.809,0.880] m`. The WASS run auto-swapped stereo order, placing the grid
reference camera at simulation `+B/2=+0.10 m`; world x therefore maps to grid x
minus 0.10 m for this ideal parallel rig.

The frozen Case 0 grid is a square inside declared truth and reconstructed
coverage:

| Parameter | Value | Unit/status | Basis |
|---|---:|---|---|
| center x | -0.10 | m, SIMULATION_TEST_PARAMETER | reference-camera offset after recorded swap |
| center y | 0.00 | m, SIMULATION_TEST_PARAMETER | ideal rig/world definition |
| area size | 1.59 | m, SIMULATION_TEST_PARAMETER | inclusive 160-node grid at 0.01 m spacing |
| N | 160 | nodes/axis, SIMULATION_TEST_PARAMETER | official square-grid format and 0.01 m spacing |
| baseline | 0.20 | m, SIMULATION_TEST_PARAMETER | Case 0 stereo configuration |
| fps | 5 | s^-1, SIMULATION_TEST_PARAMETER | timestamps 0 and 0.2 s |

This grid does not define future laboratory extent or resolution.

## Commands and return codes

With `<work>` containing `000000_wd`, `000001_wd`, and `planes.txt`, and
`<grid>` the external result directory:

```text
wassgridsurface --action generateconfig <work> <grid>
wassgridsurface --action setup <work> <grid> --gridconfig <grid>/gridconfig.txt --baseline 0.20 --fps 5
wassgridsurface --action grid <work> <grid> --gridsetup <grid>/config.mat --interpolation_algorithm DCT --parallel 1 --num_frames 2
```

All commands returned 0. Setup reported `dx=dy=0.01 m`; grid used published
DCT defaults (`Nfreqs=150`, `MAX_ITERS=500`, tolerance `1e-4`, regularizer
alpha `8e-7`, learning rate `5.0`) and stopped at iteration 100 per frame.

## Confirmed NetCDF schema

The actual NETCDF4 file has dimensions `count=2` (unlimited), `X=160`, and
`Y=160`. Root variables are `scale`, `count`, `time`, `workdir`, `X_grid`,
`Y_grid`, `Kx`, `Ky`, `Z`, `maskZ`, `cam0images`, and `cam0masks`; group `meta`
contains calibration, projections, camera-to-grid transforms, and run metadata.

`X_grid`, `Y_grid`, and `Z` are labelled millimetres; `scale` is metres and
equals 0.20. Although source dimensions are named `Z(count,X,Y)`, actual fields
prove that the first spatial index varies with y and the second with x. The
project parser verifies separability, maps storage to `[time,y,x]`, and converts
millimetres to metres.

Physical grid:

- x: `-0.895 ... +0.695 m`, increasing, `dx=0.010 m`;
- y: `-0.795 ... +0.795 m`, increasing, `dy=0.010 m`;
- Z: plane-relative elevation in `wass_plane_aligned_grid`, positive according
  to the official plane alignment's Z inversion.

## Invalid values and mask

All 51,200 Z values are finite, but `maskZ` is entirely NetCDF fill value.
Source inspection explains this: DCT returns an all-one mask while the grid
routine never calls `NetCDFOutput.set_mask`. The adapter therefore requires
`finite_z_for_dct_0_11_4`; it does not infer polarity. Coverage under this
policy is finite output coverage, not raw point-support density.

## Case 0 result and limits

```text
gridded.nc -> StandardizedGrid3D -> valid_temporal_mean -> H=Z-Z0 -> metrics
```

H truth is zero. RMSE is `4.4625202e-6 m`, MAE `3.5309726e-6 m`, maximum
absolute error `1.2276381e-5 m`, coverage `1.0`, and hole rate `0.0`. Aligned
elevation Z has RMSE `5.5410941e-4 m` about zero. Separately, the WASS plane
distance is `1.9992484686 m`, an error of `-7.515314e-4 m` from 2.00 m.

This closes ideal synthetic Case 0 only. It does not demonstrate real-camera,
real-water, or 1 cm laboratory accuracy. Case 1 and Case 2 were not attempted.
