"""Observation-anchored full-pixel water-height field solver.

The solver is backend-neutral: WASS and any calibrated dense-stereo backend
may supply observations.  Missing pixels are obtained from one explicit
regularized variational problem in physical water-plane coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

DIRECT_STEREO = np.uint8(1)
VARIATIONAL_ESTIMATE = np.uint8(2)


@dataclass(frozen=True)
class DenseHeightPolicy:
    gradient_weight: float = 2e-4
    curvature_weight: float = 2e-5
    minimum_observations: int = 12
    maximum_data_residual_m: float = 0.01
    anchor_mode: str = "soft_legacy"

    def __post_init__(self) -> None:
        if self.anchor_mode not in {"soft_legacy", "hard"}:
            raise ValueError("unknown anchor mode")
        if not all(np.isfinite(v) for v in (self.gradient_weight,self.curvature_weight,self.maximum_data_residual_m)):
            raise ValueError("policy values must be finite")
        if self.gradient_weight < 0 or self.curvature_weight < 0:
            raise ValueError("regularization weights must be non-negative")
        if self.gradient_weight == 0 and self.curvature_weight == 0:
            raise ValueError("at least one regularization weight must be positive")
        if self.minimum_observations < 1 or self.maximum_data_residual_m <= 0:
            raise ValueError("observation and residual gates must be positive")


@dataclass(frozen=True)
class DenseHeightSolution:
    height_m: np.ndarray
    source_status: np.ndarray
    confidence: np.ndarray
    metadata: dict[str, Any]


def _physical_graph(roi: np.ndarray, x_m: np.ndarray, y_m: np.ndarray) -> tuple[sparse.csr_matrix,np.ndarray]:
    """Construct a 4-neighbour incidence matrix weighted by metric distance."""
    shape=roi.shape;flat=np.flatnonzero(roi);index=np.full(roi.size,-1,np.int64);index[flat]=np.arange(len(flat))
    index=index.reshape(shape);edges=[]
    for dr,dc in ((0,1),(1,0)):
        a=roi[:shape[0]-dr or None,:shape[1]-dc or None]
        b=roi[dr:,dc:];valid=a&b
        rr,cc=np.nonzero(valid);r2,c2=rr+dr,cc+dc
        for r0,c0,r1,c1 in zip(rr,cc,r2,c2):
            distance=float(np.hypot(x_m[r1,c1]-x_m[r0,c0],y_m[r1,c1]-y_m[r0,c0]))
            if np.isfinite(distance) and distance>1e-12:edges.append((index[r0,c0],index[r1,c1],distance))
    if not edges:raise ValueError("ROI_PHYSICAL_GRAPH_EMPTY")
    rows=np.repeat(np.arange(len(edges)),2);cols=np.asarray([(a,b) for a,b,_ in edges]).ravel()
    values=np.asarray([(1/d,-1/d) for _,_,d in edges]).ravel()
    return sparse.csr_matrix((values,(rows,cols)),shape=(len(edges),len(flat))),flat


def solve_dense_height(
    observed_height_m: np.ndarray,
    observed_mask: np.ndarray,
    roi_mask: np.ndarray,
    x_m: np.ndarray,
    y_m: np.ndarray,
    *,
    observation_weight: np.ndarray | None = None,
    policy: DenseHeightPolicy = DenseHeightPolicy(),
) -> DenseHeightSolution:
    """Solve a complete ROI height field with traceable stereo anchors.

    Fit a base plane p to the anchors and solve for residual q=h-p. Legacy
    mode minimizes ``||W^(1/2)(q-q_obs)||² + λ||Bq||² + μ||B'Bq||²``.
    Hard mode minimizes only the regularizer subject to q_obs fixed exactly.
    B is the physical-distance-weighted neighbour incidence matrix. Every ROI
    connected component must contain observations. This is a discrete graph
    regularizer, not an area-consistent continuous biharmonic discretization.
    """
    observed=np.asarray(observed_height_m,float);mask=np.array(observed_mask,bool,copy=True);roi=np.asarray(roi_mask,bool)
    x=np.asarray(x_m,float);y=np.asarray(y_m,float)
    if not (observed.shape==mask.shape==roi.shape==x.shape==y.shape) or observed.ndim!=2:
        raise ValueError("all dense-height inputs must share one two-dimensional shape")
    mask &= roi & np.isfinite(observed)
    if np.count_nonzero(mask)<policy.minimum_observations:
        raise ValueError("INSUFFICIENT_DIRECT_STEREO_OBSERVATIONS")
    if np.any(roi&(~np.isfinite(x)|~np.isfinite(y))):raise ValueError("ROI_PHYSICAL_COORDINATES_UNKNOWN")
    B,flat=_physical_graph(roi,x,y);n=len(flat)
    adjacency=(abs(B).T@abs(B)).astype(bool);component_count,labels=connected_components(adjacency,directed=False)
    observed_local=mask.ravel()[flat]
    for component in range(component_count):
        if not np.any(observed_local&(labels==component)):raise ValueError("UNANCHORED_ROI_COMPONENT")
    weights=np.ones(observed.shape,float) if observation_weight is None else np.asarray(observation_weight,float)
    if weights.shape!=observed.shape or np.any(~np.isfinite(weights[mask])) or np.any(weights[mask]<=0):
        raise ValueError("observation weights must be finite and positive at observations")
    data_weight=np.zeros(n);data_weight[observed_local]=weights.ravel()[flat][observed_local]
    physical=np.column_stack((x.ravel()[flat],y.ravel()[flat]));design=np.column_stack((np.ones(n),physical))
    if np.linalg.matrix_rank(design[observed_local])<3:
        raise ValueError("OBSERVATION_SPATIAL_SUPPORT_DEGENERATE")
    plane_coefficients=np.linalg.lstsq(design[observed_local],observed.ravel()[flat][observed_local],rcond=None)[0]
    base=design@plane_coefficients
    target=np.zeros(n);target[observed_local]=observed.ravel()[flat][observed_local]-base[observed_local]
    lap=B.T@B
    regularizer=policy.gradient_weight*lap+policy.curvature_weight*(lap.T@lap)
    if policy.anchor_mode=="hard":
        # Solve missing values with observed residuals as exact Dirichlet data.
        # Unlike overwriting a soft fit afterwards, neighbouring estimates see
        # the same anchors that will be returned to the caller.
        unknown=~observed_local;correction=target.copy()
        if unknown.any():
            system=regularizer[unknown][:,unknown].tocsc()
            rhs=-(regularizer[unknown][:,observed_local]@target[observed_local])
            correction[unknown]=spsolve(system,rhs)
    else:
        system=sparse.diags(data_weight)+regularizer+sparse.eye(n)*1e-12
        correction=np.asarray(spsolve(system.tocsc(),data_weight*target),float)
    solution=base+correction
    if not np.all(np.isfinite(solution)):raise ValueError("DENSE_HEIGHT_LINEAR_SOLVE_FAILED")
    residual=solution[observed_local]-observed.ravel()[flat][observed_local]
    rms=float(np.sqrt(np.mean(residual**2)));maximum=float(np.max(np.abs(residual)))
    if rms>policy.maximum_data_residual_m:raise ValueError("DENSE_HEIGHT_DATA_RESIDUAL_GATE_FAILED")
    output=np.full(observed.shape,np.nan);output.ravel()[flat]=solution
    source=np.zeros(observed.shape,np.uint8);source[roi]=VARIATIONAL_ESTIMATE;source[mask]=DIRECT_STEREO;output[mask]=observed[mask]
    points=np.column_stack((x[mask],y[mask]));queries=np.column_stack((x[roi],y[roi]));distance=cKDTree(points).query(queries,k=1)[0]
    spacing=cKDTree(points).query(points,k=min(2,len(points)))[0][:,-1];scale=max(float(np.percentile(spacing[spacing>0],90)),1e-12)
    confidence=np.zeros(observed.shape,np.uint8);confidence_values=np.where(distance<=3*scale,2,1).astype(np.uint8);confidence[roi]=confidence_values;confidence[mask]=3
    return DenseHeightSolution(output,source,confidence,{
        "model":"OBSERVATION_ANCHORED_PHYSICAL_VARIATIONAL_SURFACE",
        "anchor_mode":policy.anchor_mode,
        "data_residual_is_accuracy_validation":False,
        "objective":("metric graph gradient and squared graph Laplacian of detrended height; exact observation constraints"
                     if policy.anchor_mode=="hard" else "weighted stereo data + metric graph regularization of detrended height"),
        "roi_pixel_count":int(roi.sum()),"direct_observation_count":int(mask.sum()),"coverage_ratio":1.0,
        "direct_ratio":float(mask.sum()/roi.sum()),"component_count":int(component_count),
        "data_residual_rmse_m":rms,"data_residual_max_m":maximum,
        "gradient_weight":policy.gradient_weight,"curvature_weight":policy.curvature_weight,
        "base_plane_coefficients_m_per_m":[float(value) for value in plane_coefficients],
        "height_unit":"m","physical_coordinate_unit":"m",
    })
