param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$BuildTools,
    [Parameter(Mandatory)][string]$BuildRoot
)

$ErrorActionPreference = 'Stop'
$devRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $BuildTools
$env:PYINSTALLER_CONFIG_DIR = Join-Path $BuildRoot 'cache'
$pythonRoot = & $Python -B -c 'import sys; print(sys.base_prefix)'
$env:PATH = "$pythonRoot;$pythonRoot\DLLs;$env:SystemRoot\System32;$env:SystemRoot"
$dist = Join-Path $BuildRoot 'dist'
$work = Join-Path $BuildRoot 'work'
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
$options = @(
    '--windowed', '--onedir', '--noupx', '--name', 'HoloKeyboard',
    '--exclude-module', 'PIL', '--exclude-module', '_hashlib', '--exclude-module', '_lzma',
    '--version-file', (Join-Path $PSScriptRoot 'version.txt'),
    '--icon', (Join-Path $devRoot 'assets\holokeyboard.ico'),
    '--add-data', "$(Join-Path $devRoot 'assets'):assets",
    '--paths', $devRoot,
    '--distpath', $dist, '--workpath', $work, '--specpath', $BuildRoot,
    (Join-Path $devRoot 'holo_keyboard_hud.py')
)
# Story files are not part of the public source/package (rights not confirmed). Bundle them only
# if a rights-confirmed 'stories' folder has been added beside the sources.
$stories = Join-Path $devRoot 'stories'
if (Test-Path -LiteralPath $stories) { $options = @('--add-data', "${stories}:stories") + $options }
& $Python -B -m PyInstaller @options
if ($LASTEXITCODE -ne 0) { throw "Packaging failed ($LASTEXITCODE)" }
# Windows 11 supplies UCRT. Use the separately installed official VC x64 runtime.
$runtime = Join-Path $dist 'HoloKeyboard\_internal'
Get-ChildItem -LiteralPath $runtime -File | Where-Object {
    $_.Name -match '^(?:api-ms-win-.*|ucrtbase|vcruntime140(?:_1)?)\.dll$'
} | ForEach-Object { Remove-Item -LiteralPath $_.FullName }
