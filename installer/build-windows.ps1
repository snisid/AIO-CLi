$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip build pyinstaller
python -m pip install -e ".[dev]"

python -m pytest -q
python -m ruff check .
python -m mypy ma_cli
python -m build

if (Test-Path "dist\ma-cli.exe") { Remove-Item "dist\ma-cli.exe" -Force }
python -m PyInstaller --onefile --name ma-cli --clean --console --paths . installer\ma_cli_launcher.py

if (-not (Test-Path "dist\ma-cli.exe")) {
  throw "PyInstaller did not produce dist\ma-cli.exe"
}

if (Get-Command iscc -ErrorAction SilentlyContinue) {
  & iscc installer\MA-CLI-Setup.iss
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
} else {
  Write-Warning "Inno Setup 6 not found. The executable was built successfully; install Inno Setup 6 and rerun this script to create the installer."
}

Write-Host ""
Write-Host "MA-CLI Windows build complete."
Write-Host "Executable: $Root\dist\ma-cli.exe"
if (Test-Path "dist\windows\MA-CLI-Setup-v1.0.0.exe") {
  Write-Host "Installer:  $Root\dist\windows\MA-CLI-Setup-v1.0.0.exe"
}
