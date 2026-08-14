# Prepare Windows installer staging directory with private Python, venv, and bundled ffmpeg.
param(
    [string] $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$Staging = Join-Path $PSScriptRoot "staging"
$Dist = Join-Path $PSScriptRoot "dist"
$VersionsFile = Join-Path $Root "packaging\common\versions.env"

if (-not (Test-Path $VersionsFile)) {
    throw "Missing versions file: $VersionsFile"
}

Get-Content $VersionsFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z0-9_]+)=(.*)$') {
        Set-Variable -Name $Matches[1] -Value $Matches[2].Trim() -Scope Script
    }
}

$PythonTag = "cpython-$PYTHON_VERSION+$PYTHON_BUILD_RELEASE-x86_64-pc-windows-msvc-install_only"
$PythonArchive = "$PythonTag.tar.gz"
$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PYTHON_BUILD_RELEASE/$PythonArchive"

function Ensure-Dir([string] $Path) {
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Download-File([string] $Url, [string] $Destination) {
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

Write-Host "Building wheel..."
Ensure-Dir $Dist
$wheel = & python -m pip wheel "$Root" -w $Dist
if ($LASTEXITCODE -ne 0) {
    & python -m pip install build
    & python -m build --wheel "$Root" -o $Dist
}

$projectWheel = Get-ChildItem -Path $Dist -Filter "karaoke_blast-*.whl" | Sort-Object Name -Descending | Select-Object -First 1
if (-not $projectWheel) {
    throw "Wheel was not produced in $Dist"
}

Write-Host "Preparing staging directory..."
if (Test-Path $Staging) {
    Remove-Item -Recurse -Force $Staging
}
Ensure-Dir $Staging

$pythonDir = Join-Path $Staging "python"
$venvDir = Join-Path $Staging "venv"
$ffmpegDir = Join-Path $Staging "ffmpeg"
$tmpDir = Join-Path $env:TEMP "karaoke-blast-staging"

if (Test-Path $tmpDir) {
    Remove-Item -Recurse -Force $tmpDir
}
Ensure-Dir $tmpDir

$pythonArchivePath = Join-Path $tmpDir $PythonArchive
Download-File $PythonUrl $pythonArchivePath

Write-Host "Extracting Python runtime..."
& tar -xzf $pythonArchivePath -C $tmpDir
$extractedPython = Join-Path $tmpDir "python"
if (-not (Test-Path $extractedPython)) {
    throw "Expected python directory after extraction"
}
Move-Item $extractedPython $pythonDir

Write-Host "Creating virtual environment..."
$pythonExe = Join-Path $pythonDir "python.exe"
& $pythonExe -m venv $venvDir

$venvPython = Join-Path $venvDir "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip wheel
& $venvPython -m pip install $projectWheel.FullName

Write-Host "Downloading bundled ffmpeg..."
Ensure-Dir $ffmpegDir
$ffmpegZip = Join-Path $tmpDir "ffmpeg.zip"
Download-File $FFMPEG_WINDOWS_URL $ffmpegZip
Expand-Archive -Path $ffmpegZip -DestinationPath $tmpDir -Force
$ffmpegExe = Get-ChildItem -Path $tmpDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if (-not $ffmpegExe) {
    throw "ffmpeg.exe not found in downloaded archive"
}
Copy-Item $ffmpegExe.FullName (Join-Path $ffmpegDir "ffmpeg.exe")

Copy-Item (Join-Path $PSScriptRoot "launcher.bat") (Join-Path $Staging "launcher.bat")
Copy-Item (Join-Path $PSScriptRoot "detect-deps.ps1") (Join-Path $Staging "detect-deps.ps1")
Copy-Item (Join-Path $Root "src\karaoke_blast\assets\icon.ico") (Join-Path $Staging "icon.ico")

Write-Host "Staging complete: $Staging"
