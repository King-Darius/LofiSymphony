<#
    Run the Streamlit app with the same hardening defaults documented in the README.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $ProjectRoot

$srcPath = Join-Path $ProjectRoot 'src'
if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = $srcPath
} elseif (-not $env:PYTHONPATH.Split([System.IO.Path]::PathSeparator) -contains $srcPath) {
    $env:PYTHONPATH = "$srcPath$([System.IO.Path]::PathSeparator)$($env:PYTHONPATH)"
}

# Mirror the local-only + no-telemetry defaults from .streamlit/config.toml.
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = 'false'

& python -m streamlit run (Join-Path $ProjectRoot 'src/lofi_symphony/app.py') @args
exit $LASTEXITCODE
