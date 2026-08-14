# Detect VLC and ffmpeg on the target machine and install only what is missing.
# Usage: powershell -ExecutionPolicy Bypass -File detect-deps.ps1 [-InstallVlc $true]

param(
    [string] $AppDir = $PSScriptRoot,
    [bool] $InstallVlc = $true
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string] $Message)
    Write-Host "[Karaoke Blast] $Message"
}

function Test-VlcInstalled {
    $dllPaths = @(
        Join-Path ${env:ProgramFiles} "VideoLAN\VLC\libvlc.dll"
        Join-Path ${env:ProgramFiles(x86)} "VideoLAN\VLC\libvlc.dll"
    )

    foreach ($path in $dllPaths) {
        if (Test-Path $path) {
            return $true
        }
    }

    $registryPaths = @(
        "HKLM:\SOFTWARE\VideoLAN\VLC",
        "HKLM:\SOFTWARE\WOW6432Node\VideoLAN\VLC"
    )

    foreach ($regPath in $registryPaths) {
        try {
            $installDir = (Get-ItemProperty -Path $regPath -ErrorAction Stop).InstallDir
            if ($installDir -and (Test-Path (Join-Path $installDir "libvlc.dll"))) {
                return $true
            }
        } catch {
            continue
        }
    }

    return $false
}

function Install-Vlc {
    Write-Log "VLC not found. Attempting installation..."

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            winget install --id VideoLAN.VLC -e --accept-package-agreements --accept-source-agreements
            if (Test-VlcInstalled) {
                Write-Log "VLC installed via winget."
                return
            }
        } catch {
            Write-Log "winget VLC install failed: $_"
        }
    }

    Write-Log "Could not install VLC automatically. Download from https://www.videolan.org/vlc/"
}

function Test-FfmpegAvailable {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        return $true
    }

    $bundled = Join-Path $AppDir "ffmpeg\ffmpeg.exe"
    return Test-Path $bundled
}

function Ensure-BundledFfmpeg {
    $bundled = Join-Path $AppDir "ffmpeg\ffmpeg.exe"
    if (Test-Path $bundled) {
        Write-Log "Bundled ffmpeg is available at $bundled"
        return
    }

    Write-Log "ffmpeg not found on PATH and no bundled copy exists in $AppDir\ffmpeg"
    Write-Log "Install ffmpeg from https://ffmpeg.org/download.html or re-run the installer."
}

Write-Log "Checking dependencies in $AppDir"

if (Test-VlcInstalled) {
    Write-Log "VLC is already installed."
} elseif ($InstallVlc) {
    Install-Vlc
} else {
    Write-Log "VLC is not installed. Local file playback will not work until VLC is installed."
}

if (Test-FfmpegAvailable) {
    Write-Log "ffmpeg is available."
} else {
    Ensure-BundledFfmpeg
}

Write-Log "Dependency check complete."
