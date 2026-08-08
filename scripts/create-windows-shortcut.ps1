# Create a Desktop shortcut that launches Karaoke Blast.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\create-windows-shortcut.ps1

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AppName = "Karaoke Blast"
$IconPath = Join-Path $Root "src\karaoke_blast\assets\icon.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "$AppName.lnk"

function Resolve-Python {
    $pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
    $python = Join-Path $Root ".venv\Scripts\python.exe"

    if (-not (Test-Path $python)) {
        throw "Virtualenv Python not found at $python. Run: python -m venv .venv"
    }

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $null = & $python -c "import karaoke_blast" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "karaoke_blast is not installed in the venv. Run: .\.venv\Scripts\pip install -e ."
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }

    if (Test-Path $pythonw) {
        return $pythonw
    }
    return $python
}

$Python = Resolve-Python
Write-Host "Using Python: $Python"

if (-not (Test-Path $IconPath)) {
    throw "Icon not found: $IconPath"
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Python
$Shortcut.Arguments = "-m karaoke_blast"
$Shortcut.WorkingDirectory = $Root
$Shortcut.IconLocation = "$IconPath,0"
$Shortcut.Description = "Open Karaoke Blast"
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
