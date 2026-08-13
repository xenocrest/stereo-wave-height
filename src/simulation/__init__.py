"""Hardware-free observation geometry driven by project configuration."""

from .config import CandidateCameraParameters, NominalIntrinsics, load_nominal_intrinsics
from .manifest import SyntheticDatasetManifest, build_synthetic_manifest
from .stereo_rig import IdealStereoRig
from .surfaces import SurfaceTruth, constant_height, sinusoidal_wave, static_water
from .irregular_surface import WaveComponent, component_height_m, multicomponent_wave

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
    "WaveComponent",
    "component_height_m",
    "multicomponent_wave",
    "static_water",
]
