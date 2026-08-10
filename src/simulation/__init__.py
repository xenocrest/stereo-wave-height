"""Hardware-free observation geometry driven by project configuration."""

from .config import CandidateCameraParameters, NominalIntrinsics, load_nominal_intrinsics
from .manifest import SyntheticDatasetManifest, build_synthetic_manifest
from .stereo_rig import IdealStereoRig
from .surfaces import SurfaceTruth, constant_height, sinusoidal_wave, static_water

__all__ = [
    "CandidateCameraParameters",
    "IdealStereoRig",
    "NominalIntrinsics",
    "SurfaceTruth",
    "SyntheticDatasetManifest",
    "build_synthetic_manifest",
    "constant_height",
    "load_nominal_intrinsics",
    "sinusoidal_wave",
    "static_water",
]
