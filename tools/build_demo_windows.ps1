param(
    [string]$PythonExe = "python",
    [string]$WassBin = "D:\wass\dist\bin",
    [string]$PolicyStereo = "D:\wass_diagnostic\build_policy460c\wass_stereo\Release\wass_stereo.exe",
    [string]$WassConfig = "D:\stereo-wave-height-runs\HomeTank_004\phase4-case2-candidate02-20260828\reconstruction\wass_workspace\config",
    [string]$FfmpegRoot = "D:\FormatFactory"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Build = Join-Path $Repo "build"
$Dist = Join-Path $Repo "dist"

function Assert-ChildPath([string]$Path, [string]$Parent) {
    $candidate = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $root = [IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    if (-not $candidate.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing operation outside repository: $candidate"
    }
}

foreach ($required in @(
    (Join-Path $Repo "packaging\demo_entry.py"), $WassBin, $PolicyStereo, $WassConfig,
    (Join-Path $FfmpegRoot "ffmpeg.exe")
)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required packaging input missing: $required" }
}

& $PythonExe -c "import PyInstaller, cv2" 2>$null
if ($LASTEXITCODE -ne 0) { throw "PyInstaller and opencv-python are required; OpenCV is used by the existing video-calibration workflow." }

foreach ($target in @($Build, $Dist)) {
    Assert-ChildPath $target $Repo
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}

Push-Location $Repo
try {
    & $PythonExe -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name StereoWaveHeightDemo `
        --paths $Repo --paths (Join-Path $Repo "src") `
        --hidden-import src.reconstruction.run_single_frame `
        --hidden-import matplotlib.backends.backend_tkagg `
        (Join-Path $Repo "packaging\demo_entry.py")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }

$App = Join-Path $Dist "StereoWaveHeightDemo"
$Resource = Join-Path $App "resources\HomeTank_004"
$Resource005 = Join-Path $App "resources\HomeTank_005"
$RuntimeWass = Join-Path $App "runtime\wass"
$RuntimeFfmpeg = Join-Path $App "runtime\ffmpeg"
New-Item -ItemType Directory -Force -Path $Resource, $Resource005, (Join-Path $Resource "manual_reference"), (Join-Path $Resource "wass_config"), $RuntimeWass, $RuntimeFfmpeg | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Resource005 "wass_config") | Out-Null

Copy-Item -LiteralPath (Join-Path $Repo "packaging\resources\HomeTank_004\single_frame_dense_template.yaml") -Destination $Resource
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_004\calibration_result.yaml") -Destination $Resource
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_004\static_reference_plane.yaml") -Destination $Resource
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_004\manual_reference\frozen_cam1_validation_mapping.yaml") -Destination (Join-Path $Resource "manual_reference")
Copy-Item -Path (Join-Path $WassConfig "*") -Destination (Join-Path $Resource "wass_config") -Recurse
Copy-Item -Path (Join-Path $WassConfig "*") -Destination (Join-Path $Resource005 "wass_config") -Recurse
Copy-Item -Path (Join-Path $WassBin "*") -Destination $RuntimeWass -Recurse
Copy-Item -LiteralPath $PolicyStereo -Destination (Join-Path $RuntimeWass "wass_stereo_policy.exe")
Copy-Item -LiteralPath (Join-Path $Repo "packaging\runtime_binding.json") -Destination (Join-Path $RuntimeWass "runtime_binding.json")
Copy-Item -LiteralPath (Join-Path $FfmpegRoot "ffmpeg.exe") -Destination $RuntimeFfmpeg
Get-ChildItem -LiteralPath $FfmpegRoot -Filter "*.dll" -File | Copy-Item -Destination $RuntimeFfmpeg
Copy-Item -LiteralPath (Join-Path $Repo "DEMO_RUN.md") -Destination $App
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_005\calibration_adaptive\adaptive_calibration.yaml") -Destination $Resource005
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_005\DEMO_READINESS_REPORT.md") -Destination $Resource005
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_005\demo_run_template.yaml") -Destination $Resource005
Copy-Item -LiteralPath (Join-Path $Repo "packaging\resources\HomeTank_005\single_frame_dense_template.yaml") -Destination $Resource005
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_005\demo_reference_artifact.yaml") -Destination $Resource005
Copy-Item -LiteralPath (Join-Path $Repo "experiments\real_video\HomeTank_005\demo_full_pixel_config.yaml") -Destination $Resource005
Copy-Item -Path (Join-Path $Repo "experiments\real_video\HomeTank_005\calibrations") -Destination $Resource005 -Recurse
Copy-Item -Path (Join-Path $Repo "experiments\real_video\HomeTank_005\demo_common_fov") -Destination $Resource005 -Recurse
Copy-Item -Path (Join-Path $Repo "experiments\real_video\HomeTank_005\demo_full_pixel_result") -Destination $Resource005 -Recurse

$exe = Join-Path $App "StereoWaveHeightDemo.exe"
$Review = Join-Path $Repo "resources\wass_observation_review"
if (Test-Path -LiteralPath (Join-Path $Review "review.json")) {
    Copy-Item -LiteralPath $Review -Destination (Join-Path $App "resources") -Recurse
}
if (-not (Test-Path -LiteralPath $exe)) { throw "Packaged executable missing: $exe" }
Write-Host "Windows offline demo built: $exe"
