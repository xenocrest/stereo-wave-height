"""Register a full asymmetric-parity checkerboard without inferred corners."""
from __future__ import annotations

import numpy as np


def parity_contrast(gray: np.ndarray, grid: np.ndarray) -> float:
    """Measured cell polarity contrast; odd/even dimensions resolve 180 degrees.

    Requires observed corners in image-ordered row/column topology. This is not
    an absolute marker ID: a designated physical reference view fixes polarity.
    """
    image=np.asarray(gray);p=np.asarray(grid,float)
    if image.ndim!=2 or p.ndim!=3 or p.shape[2]!=2 or min(p.shape[:2])<3:
        raise ValueError('grayscale image and observed [row,column,2] grid required')
    rows,cols=p.shape[:2]
    if (rows+cols)%2==0:raise ValueError('180-degree polarity is ambiguous for this pattern')
    centers=(p[:-1,:-1]+p[1:,:-1]+p[:-1,1:]+p[1:,1:])/4
    values=[]
    for row in centers:
        line=[]
        for x,y in row:
            x,y=round(float(x)),round(float(y))
            if x<2 or y<2 or x>=image.shape[1]-2 or y>=image.shape[0]-2:
                raise ValueError('cell sampling outside image')
            line.append(float(np.median(image[y-2:y+3,x-2:x+3])))
        values.append(line)
    values=np.array(values);yy,xx=np.indices(values.shape);a=(xx+yy)%2==0
    return float(np.median(values[a])-np.median(values[~a]))


def register_parity(grid: np.ndarray, contrast: float, reference_contrast: float,
                    minimum_contrast: float=10.) -> tuple[np.ndarray,bool]:
    """Return reordered real observations, never add or move a point."""
    if not np.isfinite(contrast) or not np.isfinite(reference_contrast) or min(abs(contrast),abs(reference_contrast))<minimum_contrast:
        raise ValueError('board polarity not observable')
    flip=bool(contrast*reference_contrast<0)
    return (np.asarray(grid)[::-1,::-1].copy() if flip else np.asarray(grid).copy()),flip
