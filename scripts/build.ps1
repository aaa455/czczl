param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean ZuJiChangZheng.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    Write-Output 'Built: dist/ZuJiChangZheng.exe'
} finally {
    Pop-Location
}
