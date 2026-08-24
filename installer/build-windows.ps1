$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python -m pip install --upgrade build pyinstaller
python -m pip install -e '.[dev]'
python -m pytest -q
python -m build
python -m PyInstaller --onefile --name ma-cli --clean --console ma_cli/cli/main.py
if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc installer\MA-CLI-Setup.iss
} else {
    Write-Warning 'Inno Setup 6 (iscc) not found; executable/package were built.'
}
