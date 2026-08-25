# HomeTank_004 Pixel–XYZ and Height Result

## Scope

The generic reconstruction pipeline now preserves a traceable pixel-to-XYZ product and computes height as signed orthogonal distance to a declared reference plane. Inputs are limited to stereo images, unchanged OpenCV `K/D/R/T`, and WASS outputs. No ruler measurement, manual scale or external height correction enters reconstruction.

Status: **`PIXEL_XYZ_HEIGHT_FOUNDATION_COMPLETED_WITH_EXISTING_WARNINGS`**. This confirms the software interface, not static stability or physical wave accuracy.

## Pixel–XYZ correspondence

`mesh_cam.xyzC` contains XYZ but no stored pixel index. Each unscaled WASS camera point is therefore projected with that frame's WASS-generated `P0cam.txt`; the resulting rectified `(u,v)` is paired with the same point after explicit baseline scaling to metres. Projection uses unscaled camera points because the translation column in `P0cam` is in the WASS camera unit.

WASS auto-swapped the HomeTank_004 inputs. The mapping coordinate system is consequently recorded as `wass_rectified_computational_cam0__input_right`; it is not mislabeled as original left or unrectified pixels.

| Frame | Correspondences | u range (px) | v range (px) |
|---|---:|---:|---:|
| 000000 | 142,444 | 912.601–1071.996 | 348.872–781.245 |
| 000001 | 221,307 | 687.674–1114.532 | 304.308–785.241 |
| 000002 | 191,312 | 671.479–1210.813 | 293.058–783.754 |
| 000003 | 201,904 | 714.642–1272.188 | 313.841–773.994 |
| 000004 | 198,554 | 818.730–1145.524 | 276.530–779.838 |

Total: **955,521** pixel–XYZ pairs. Querying uses the nearest observed projected point only within a caller-supplied pixel-radius gate; missing pixels fail explicitly. No dense interpolation is claimed.

## XYZ and height

| Item | Result |
|---|---|
| XYZ points | 955,521 |
| X range | −0.151868 to −0.010290 m |
| Y range | −0.094456 to +0.008201 m |
| Z range | +0.248815 to +0.364975 m |
| height range | −0.026767 to +0.093137 m |

The static reference plane is

$$
n=(0.4266091,0.0675784,0.9019079),\qquad D=-0.2246730\ \mathrm{m}.
$$

For metric point $P=(X,Y,Z)$, height is

$$
H(P)=\frac{n\cdot P+D}{\lVert n\rVert}.
$$

Camera Z is not used as height. Recomputing all five existing products with the new module gives a maximum difference of exactly **0 m** from the previously saved pipeline heights, confirming that the extracted implementation preserves the existing geometry.

## Independence and limitations

The pipeline imports neither ruler configuration nor ruler validation code. The ruler remains a downstream independent check of reconstructed scale and height. HomeTank_004 retains `CALIBRATION_QUALITY_FAIL`, `STATIC_VALIDATION_FAIL`, candidate synchronization and unvalidated physical wave height; this result does not change those conclusions.

The corresponding compressed mapping files were generated under the repository-external run directory and are not committed. Future professional stereo runs will receive the same output automatically from the pipeline.
