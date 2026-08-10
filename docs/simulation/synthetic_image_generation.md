# Synthetic Stereo Image Generation

## Scope

This module converts an analytical water-surface truth into a small pairwise
stereo image dataset for the WASS input boundary. It validates ideal projection,
dataset organisation, and metadata propagation. It does **not** validate WASS,
real water optics, camera performance, or the 1 cm real-water objective.

The chain is:

`SurfaceTruth -> shared physical texture -> ideal left/right projection -> mono8 PNG pairs -> WASS input boundary`

No stereo matching, triangulation, autocalibration, or reconstruction is
performed by this module. Those responsibilities remain with WASS.

## Inputs and provenance

The nominal camera is loaded from
`configs/equipment/candidate_system.yaml`. The generated image dimensions are
2448 px by 2048 px, the candidate pixel size is 3.45 um, and the candidate
focal length is 8 mm. The resulting pixel focal length is a
`SIMULATION_NOMINAL` value, not a calibration result. The principal point at
the image centre and zero distortion are ideal-simulation assumptions.

Baseline `B` (m) and working distance `Z` (m) remain required deployment
inputs. The generator supplies no defaults for either value and does not select
a final rig geometry.

Supported truth models are the existing mathematical cases:

- Case 0: `H_true = 0` (static water);
- Case 1: `H_true = constant` (signed fixed-height plane);
- Case 2: `H_true = A sin(k x - omega t + phase)` (regular 1-D wave).

All surface coordinates and heights are in metres; timestamps are integer
nanoseconds. The world coordinate system is `world_water_surface`.

## Ideal image model

Each `(X,Y,Z)` surface sample is projected through the existing ideal pinhole
camera. A deterministic unsigned 8-bit random value is attached to every
physical `(x,y)` sample. Both cameras therefore observe the same physical
texture rather than two independently generated images.

Projected samples are rounded to pixels and rasterised with an explicit square
splat radius. When samples collide, the sample with the smallest positive
camera depth is retained. The splat is a numerical rasterisation setting only;
it is not a point-spread, illumination, reflection, refraction, BRDF, or noise
model. Background pixels are zero by default.

## Dataset output

`generate_stereo_dataset` writes:

```text
simulation_dataset/
  left/000000.png
  right/000000.png
  calibration/camera.yaml
  metadata/manifest.json
  ground_truth/height_fields.npz
```

Images are 8-bit grayscale PNG (`mono8`). This is the current WASS input
adaptation format; it is not asserted to be the native output format of the
candidate industrial camera. Existing non-empty output directories are never
overwritten.

The manifest records frame identifiers, nanosecond timestamps, relative image
paths, candidate camera identity and parameters, explicit deployment variables,
texture seed, surface model, coordinate system, units, calibration reference,
and ground-truth reference. The compressed truth file contains `x_m`, `y_m`,
`timestamp_ns`, `z0_m`, `h_true_m`, and `z_true_m`.

## Limitations and real-device relationship

- The candidate MER2-503-36U3C and 8 mm lens are not treated as purchased or
  calibrated equipment.
- Real intrinsics, principal point, distortion, radiometric response, exposure,
  trigger timing, and water-surface optical behaviour remain UNKNOWN/TODO.
- Random planar texture is an artificial matching target, not a real sea image.
- No large image sequence or video is stored in the repository; tests generate
  one-frame datasets in temporary directories.
- Passing these tests establishes only internal geometric and interface
  consistency. It cannot establish real-water centimetre accuracy.
