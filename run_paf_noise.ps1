$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$cli = Join-Path $root "src\paf_noise_cli\cli.py"

if (-not (Test-Path $python)) {
    throw "Python virtualenv non trovato in $python"
}

if (-not (Test-Path $cli)) {
    throw "CLI non trovato in $cli"
}

& $python $cli @args
exit $LASTEXITCODE
