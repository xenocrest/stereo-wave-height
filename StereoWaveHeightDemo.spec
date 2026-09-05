# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/research/stereo-wave-height/packaging/demo_entry.py'],
    pathex=['D:/research/stereo-wave-height', 'D:/research/stereo-wave-height/src'],
    binaries=[],
    datas=[('D:/research/stereo-wave-height/experiments/real_video/HomeTank_005/demo_reference_artifact.yaml', 'resources/HomeTank_005'), ('D:/research/stereo-wave-height/packaging/resources/HomeTank_005/single_frame_dense_template.yaml', 'resources/HomeTank_005'), ('D:/research/stereo-wave-height/experiments/real_video/HomeTank_005/calibrations/HomeTank_005_demo_only_v1/manifest.yaml', 'resources/HomeTank_005'), ('D:/research/stereo-wave-height/experiments/real_video/HomeTank_005/calibrations/HomeTank_005_demo_only_v1/opencv_calibration.yaml', 'resources/HomeTank_005/calibrations/HomeTank_005_demo_only_v1')],
    hiddenimports=['src.reconstruction.run_single_frame', 'matplotlib.backends.backend_tkagg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StereoWaveHeightDemo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StereoWaveHeightDemo',
)
