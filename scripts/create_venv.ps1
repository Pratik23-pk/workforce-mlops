param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

function Test-PythonVersion {
    param([string]$Exe)
    try {
        $version = & $Exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -ne 0) { return $false }
        $parts = $version.Split(".")
        if ($parts.Length -lt 2) { return $false }
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        return ($major -eq 3 -and $minor -ge 11 -and $minor -lt 13)
    }
    catch {
        return $false
    }
}

$candidates = @($PythonExe, "py", "python3.12", "python3.11", "python3", "python")
$selected = $null

foreach ($candidate in $candidates) {
    if (Test-PythonVersion -Exe $candidate) {
        $selected = $candidate
        break
    }
}

if (-not $selected) {
    throw "Python 3.11 or 3.12 not found. Install a supported Python and rerun."
}

Write-Host "Using Python interpreter: $selected"
& $selected -m venv .venv

Write-Host "Virtual environment created."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Then run:"
Write-Host "  python -m pip install --upgrade pip"
Write-Host "  pip install -r requirements.txt"
