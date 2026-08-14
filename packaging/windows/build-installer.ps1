# Build the Windows installer (.exe) from staging + Inno Setup.
param(
    [string] $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$PrepareScript = Join-Path $PSScriptRoot "prepare-staging.ps1"
$IssFile = Join-Path $PSScriptRoot "karaoke-blast.iss"
$DistDir = Join-Path $PSScriptRoot "dist"

& $PrepareScript -Root $Root

$version = (Select-String -Path (Join-Path $Root "pyproject.toml") -Pattern '^version = "(.*)"' | ForEach-Object { $_.Matches[0].Groups[1].Value })
if (-not $version) {
    $version = "0.1.0"
}

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $defaultIscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultIscc) {
        $iscc = $defaultIscc
    } else {
        throw "Inno Setup compiler (iscc) not found. Install from https://jrsoftware.org/isinfo.php"
    }
} else {
    $iscc = $iscc.Source
}

Push-Location $PSScriptRoot
try {
    & $iscc "/DAppVersion=$version" $IssFile
} finally {
    Pop-Location
}

$installer = Get-ChildItem -Path $DistDir -Filter "KaraokeBlast-Setup.exe" | Select-Object -First 1
if ($installer) {
    Write-Host "Built installer: $($installer.FullName)"
} else {
    throw "Installer was not produced in $DistDir"
}
