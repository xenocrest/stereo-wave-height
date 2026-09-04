"""Continuous physical-coordinate quadratic surface for refractive experiments.

An integrable six-parameter hypothesis, NOT measured per-pixel ground truth.
The caller must verify image support, ambiguity and physical accuracy before use.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class QuadraticWaterSurface:
    """H(x,y)=L*(a0+a1*x/L+a2*y/L+a3*x²/L²+a4*xy/L²+a5*y²/L²).

    Frame n is unit upward normal; e1/e2 span the reference water plane.
    Offset c defines n.P+c=0. Origin must lie in that plane. All lengths m.
    Coefficients are dimensionless. Positive height points toward n.
    """
    normal: np.ndarray
    offset_m: float
    origin_m: np.ndarray
    e1: np.ndarray
    e2: np.ndarray
    scale_m: float
    coefficients: np.ndarray

    def __post_init__(self):
        n,o,e1,e2,a=[np.asarray(x,float) for x in [self.normal,self.origin_m,self.e1,self.e2,self.coefficients]]
        if any(x.shape!=(3,) for x in [n,o,e1,e2]) or a.shape!=(6,):raise ValueError('invalid surface shapes')
        if not all(np.isfinite(x).all() for x in [n,o,e1,e2,a]):raise ValueError('UNKNOWN/nonfinite surface input')
        if not np.isfinite(self.offset_m) or not np.isfinite(self.scale_m) or self.scale_m<=0:raise ValueError('invalid meter scale')
        basis=np.stack([n,e1,e2])
        if not np.allclose(basis@basis.T,np.eye(3),atol=1e-8):raise ValueError('surface basis must be orthonormal')
        if abs(n@o+self.offset_m)>1e-8:raise ValueError('origin must lie in reference plane')

    def height_and_normal(self,points):
        """Evaluate the hypothesis and its analytic (integrable) upward normal."""
        p=np.asarray(points,float);xy=p-self.origin_m
        x=xy@self.e1/self.scale_m;y=xy@self.e2/self.scale_m;a=self.coefficients
        height=self.scale_m*(a[0]+a[1]*x+a[2]*y+a[3]*x*x+a[4]*x*y+a[5]*y*y)
        gx=a[1]+2*a[3]*x+a[4]*y;gy=a[2]+a[4]*x+2*a[5]*y
        N=self.normal-gx[...,None]*self.e1-gy[...,None]*self.e2
        return height,N/np.linalg.norm(N,axis=-1,keepdims=True)

    def intersect(self,center_m,rays):
        """Nearest positive analytic ray intersection; absent roots return NaN.

        A local quadratic is not extrapolated into a certified full water domain.
        Callers must separately gate domain and single-interface validity.
        """
        C=np.asarray(center_m,float);v=np.asarray(rays,float);a=self.coefficients;L=self.scale_m
        x0=(C-self.origin_m)@self.e1;y0=(C-self.origin_m)@self.e2
        vx=v@self.e1;vy=v@self.e2
        A=-(a[3]*vx*vx+a[4]*vx*vy+a[5]*vy*vy)/L
        B=v@self.normal-a[1]*vx-a[2]*vy-(2*a[3]*x0*vx+a[4]*(x0*vy+y0*vx)+2*a[5]*y0*vy)/L
        D=C@self.normal+self.offset_m-L*a[0]-a[1]*x0-a[2]*y0-(a[3]*x0*x0+a[4]*x0*y0+a[5]*y0*y0)/L
        linear=abs(A)<1e-12;disc=B*B-4*A*D
        sqrt=np.sqrt(np.maximum(disc,0));q=-.5*(B+np.where(B>=0,1.,-1.)*sqrt)
        with np.errstate(divide='ignore',invalid='ignore'):
            r1=q/A;r2=D/q;line=-D/B
        r1=np.where((r1>0)&(disc>=0),r1,np.inf);r2=np.where((r2>0)&(disc>=0),r2,np.inf)
        t=np.where(linear,np.where(line>0,line,np.inf),np.minimum(r1,r2))
        valid=np.isfinite(t)
        P=C+np.where(valid,t,np.nan)[:,None]*v
        h,N=self.height_and_normal(P)
        valid &= np.isfinite(P).all(1)&(np.sum(v*N,axis=1)<0)
        P[~valid]=np.nan;N[~valid]=np.nan;h[~valid]=np.nan
        return P,N,h,valid
