$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m pip install --upgrade build pyinstaller
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
python -m PyInstaller --onefile --name ma-cli --clean --console ma_cli/cli/main.py
if (Get-Command iscc -ErrorAction SilentlyContinue) {
  iscc installer\MA-CLI-Setup.iss
} else {
  Write-Warning "Inno Setup 6 not found. Install it and rerun this script to produce the installer."
}
