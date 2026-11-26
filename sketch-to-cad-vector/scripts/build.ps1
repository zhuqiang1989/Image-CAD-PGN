# build.ps1 - one-command pipeline: SVG -> PNG -> DXF -> checks -> optional cleanup.
# Keep this file ASCII-only: Windows PowerShell 5.1 reads BOM-less files as ANSI,
# which turns Chinese comments into mojibake and breaks parsing.
#
# Usage:
#   .\build.ps1 -Svg C:\out\draw.svg                     # SVG exists: render + dxf + check
#   .\build.ps1 -Svg C:\out\draw.svg -Gen                # use gen_container.py first
#   .\build.ps1 -Svg C:\out\draw.svg -Script C:\gen_x.py # use any generator script first
#   .\build.ps1 -Svg C:\out\draw.svg -Gen -Clean         # final build: keep only png+dxf
#   .\build.ps1 -Svg ... -Measure                        # also run component_geom probe
#
# -Clean removes the SVG, any *_preview.png and scripts\__pycache__ after a successful
# build, so the only deliverables left are .png and .dxf (per skill delivery rule).
param(
    [Parameter(Mandatory = $true)][string]$Svg,
    [switch]$Gen,
    [string]$Script = "",
    [double]$HeadRatio = 0.25,
    [double]$StraightRatio = 2.0,
    [int]$Thr = 170,
    [switch]$NoDxf,
    [switch]$Measure,
    [switch]$Preview,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONDONTWRITEBYTECODE = "1"   # do not create __pycache__ during the build
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$png = [IO.Path]::ChangeExtension($Svg, ".png")
$prevPath = [IO.Path]::ChangeExtension($Svg, "_preview.png")

if ($Script) {
    python $Script $Svg
    if ($LASTEXITCODE -ne 0) { throw "generator script failed: $Script" }
}
elseif ($Gen) {
    python "$here\gen_container.py" $Svg --head-ratio $HeadRatio --straight-ratio $StraightRatio
    if ($LASTEXITCODE -ne 0) { throw "gen_container failed" }
}
elseif (-not (Test-Path $Svg)) { throw "SVG not found: $Svg" }

if ($Preview) {
    python "$here\render_svg.py" $Svg $png --scale 1 --preview $prevPath
} else {
    python "$here\render_svg.py" $Svg $png --scale 1
}
if ($LASTEXITCODE -ne 0) { throw "render_svg failed" }

if ($Measure) {
    Write-Host "`n--- check: outline measures ---" -ForegroundColor Cyan
    python "$here\component_geom.py" $png --thr=$Thr --dil=1
}

if (-not $NoDxf) {
    $dxf = [IO.Path]::ChangeExtension($Svg, ".dxf")
    Write-Host "`n--- write DXF ---" -ForegroundColor Cyan
    python "$here\svg2dxf.py" $Svg $dxf
    if ($LASTEXITCODE -ne 0) {
        throw "svg2dxf failed (DXF may be open/locked in CAD - close it and rerun). SVG kept so PNG/DXF stay consistent."
    }
    Write-Host "`n--- check: DXF text style ---" -ForegroundColor Cyan
    python "$here\dxf_check.py" $dxf | Select-Object -First 6
}

if ($Clean) {
    if (Test-Path $Svg) { Remove-Item -LiteralPath $Svg -Force }
    if (Test-Path $prevPath) { Remove-Item -LiteralPath $prevPath -Force }
    $pyc = Join-Path $here "__pycache__"
    if (Test-Path $pyc) { Remove-Item -LiteralPath $pyc -Recurse -Force }
    Write-Host "`ncleaned: SVG / preview / __pycache__ removed; only png+dxf kept" -ForegroundColor Yellow
}

Write-Host "`noutputs:`n  $png" -ForegroundColor Green
if (-not $NoDxf) { Write-Host "  $([IO.Path]::ChangeExtension($Svg, '.dxf'))" -ForegroundColor Green }
Write-Host "before delivery: read the PNG once; verify nozzle direction with probe.py if unsure" -ForegroundColor Yellow