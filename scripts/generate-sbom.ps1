[CmdletBinding()]
param(
    [ValidateSet("source", "backend-image")]
    [string]$Target = "source",

    [string]$OutputDir = "sbom",

    [string]$ImageName = "station-de-recharge-backend:sbom",

    [switch]$UseDockerSyft
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$ProjectName = "station-de-recharge"
$CycloneDxPath = Join-Path $OutputDir "$ProjectName.cdx.json"
$SpdxPath = Join-Path $OutputDir "$ProjectName.spdx.json"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Invoke-LocalSyft {
    param(
        [string]$Source,
        [switch]$UseConfig
    )

    if (-not (Get-Command syft -ErrorAction SilentlyContinue)) {
        throw "Syft is not installed. Install it with 'winget install Anchore.Syft' or rerun with -UseDockerSyft for a source scan."
    }

    $SyftArgs = @("scan", $Source)

    if ($UseConfig) {
        $SyftArgs += @("--config", ".syft.yaml")
    }

    $SyftArgs += @(
        "-o", "cyclonedx-json=$CycloneDxPath",
        "-o", "spdx-json=$SpdxPath"
    )

    & syft @SyftArgs
}

function Invoke-DockerSyftForSource {
    $DockerSource = "/work"
    $DockerOutputDir = ($OutputDir -replace "\\", "/").TrimEnd("/")
    $DockerCycloneDxPath = "/work/$DockerOutputDir/$ProjectName.cdx.json"
    $DockerSpdxPath = "/work/$DockerOutputDir/$ProjectName.spdx.json"

    & docker run --rm `
        -v "${RepoRoot}:/work" `
        -w /work `
        anchore/syft:v1.42.4 `
        scan $DockerSource `
        --config /work/.syft.yaml `
        -o "cyclonedx-json=$DockerCycloneDxPath" `
        -o "spdx-json=$DockerSpdxPath"
}

function Invoke-DockerSyftForImage {
    param([string]$Source)

    $DockerOutputDir = ($OutputDir -replace "\\", "/").TrimEnd("/")
    $DockerCycloneDxPath = "/work/$DockerOutputDir/$ProjectName.cdx.json"
    $DockerSpdxPath = "/work/$DockerOutputDir/$ProjectName.spdx.json"

    & docker run --rm `
        -v /var/run/docker.sock:/var/run/docker.sock `
        -v "${RepoRoot}:/work" `
        -w /work `
        anchore/syft:v1.42.4 `
        scan $Source `
        -o "cyclonedx-json=$DockerCycloneDxPath" `
        -o "spdx-json=$DockerSpdxPath"
}

if ($Target -eq "backend-image") {
    & docker build -t $ImageName ./backend

    if ($UseDockerSyft) {
        Invoke-DockerSyftForImage -Source $ImageName
    }
    else {
        Invoke-LocalSyft -Source $ImageName
    }
}
elseif ($UseDockerSyft) {
    Invoke-DockerSyftForSource
}
else {
    Invoke-LocalSyft -Source "." -UseConfig
}

Write-Host "SBOM generated:"
Write-Host " - $CycloneDxPath"
Write-Host " - $SpdxPath"
