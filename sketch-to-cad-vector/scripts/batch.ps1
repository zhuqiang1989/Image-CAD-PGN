# batch.ps1 - build many SVGs at once: each -> PNG + DXF, optional merge, then clean.
# Keep ASCII-only (Windows PowerShell 5.1 ANSI pitfall).
#
# The model reads each source image and writes a geometry SVG (via cadkit / a gen
# script) into -SvgDir. This helper renders them all into -OutDir and optionally
# merges the DXFs into one file. Source SVGs are intermediates and are removed.
#
# Usage:
#   .\batch.ps1 -SvgDir C:\work\svg -OutDir C:\out                 # separate DXF per image
#   .\batch.ps1 -SvgDir C:\work\svg -OutDir C:\out -Merge          # also one merged.dxf
#   .\batch.ps1 -SvgDir ... -OutDir ... -Merge -Cols 3 -KeepSvg
param(
    [Parameter(Mandatory = $true)][string]$SvgDir,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [switch]$Merge,
    [int]$Cols = 2,
    [double]$Gap = 60,
    [switch]$KeepSvg
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$svgs = Get-ChildItem -LiteralPath $SvgDir -Filter *.svg -File
if (-not $svgs) { throw "no .svg found in $SvgDir" }
$dxfList = @()

foreach ($f in $svgs) {
    $base = [IO.Path]::GetFileNameWithoutExtension($f.Name)
    $png = Join-Path $OutDir "$base.png"
    $dxf = Join-Path $OutDir "$base.dxf"
    Write-Host "`n=== $base ===" -ForegroundColor Cyan
    python "$here\render_svg.py" $f.FullName $png --scale 1
    if ($LASTEXITCODE -ne 0) { throw "render failed: $($f.Name)" }
    python "$here\svg2dxf.py" $f.FullName $dxf
    if ($LASTEXITCODE -ne 0) { throw "dxf failed: $($f.Name)" }
    $dxfList += $dxf
}

if ($Merge) {
    $merged = Join-Path $OutDir "merged.dxf"
    Write-Host "`n=== merge -> $merged ===" -ForegroundColor Cyan
    python "$here\merge_dxf.py" @dxfList -o $merged --cols $Cols --gap $Gap
    if ($LASTEXITCODE -ne 0) { throw "merge failed" }
}

if (-not $KeepSvg) {
    foreach ($f in $svgs) { Remove-Item -LiteralPath $f.FullName -Force }
    $pyc = Join-Path $here "__pycache__"
    if (Test-Path $pyc) { Remove-Item -LiteralPath $pyc -Recurse -Force }
    Write-Host "`ncleaned source SVGs / __pycache__; OutDir keeps png+dxf only" -ForegroundColor Yellow
}

Write-Host "`nbatch done: $($svgs.Count) image(s) -> $OutDir" -ForegroundColor Green