[CmdletBinding()]
param(
    [ValidateSet("source", "backend-image")]
    [string]$Target = "source",

    [string]$OutputDir = "sbom",

    [string]$ImageName = "station-de-recharge-backend:sbom",

    [switch]$UseDockerSyft,

    [switch]$AnalyzeVulnerabilities,

    [switch]$UseDockerGrype,

    [string[]]$VexDocuments = @("security/vex.openvex.json")
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$ProjectName = "station-de-recharge"
$CycloneDxPath = Join-Path $OutputDir "$ProjectName.cdx.json"
$SpdxPath = Join-Path $OutputDir "$ProjectName.spdx.json"
$VulnerabilityJsonPath = Join-Path $OutputDir "$ProjectName.vulnerabilities.json"
$VulnerabilitySarifPath = Join-Path $OutputDir "$ProjectName.vulnerabilities.sarif"
$VexDraftPath = Join-Path $OutputDir "$ProjectName.openvex.json"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Use-HttpsCycloneDxSchema {
    if (-not (Test-Path $CycloneDxPath)) {
        return
    }

    $Content = Get-Content -Raw -Path $CycloneDxPath
    $UpdatedContent = $Content.Replace(
        '"$schema": "http://cyclonedx.org/schema/',
        '"$schema": "https://cyclonedx.org/schema/'
    )

    if ($UpdatedContent -ne $Content) {
        $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText((Resolve-Path $CycloneDxPath), $UpdatedContent, $Utf8NoBom)
    }
}

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

function Get-ProductId {
    if ($Target -eq "backend-image") {
        $TagSeparatorIndex = $ImageName.LastIndexOf(":")

        if ($TagSeparatorIndex -gt 0) {
            $Repository = $ImageName.Substring(0, $TagSeparatorIndex)
            $Tag = $ImageName.Substring($TagSeparatorIndex + 1)
        }
        else {
            $Repository = $ImageName
            $Tag = "latest"
        }

        $ImageId = (& docker image inspect $ImageName --format "{{.Id}}" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $ImageId) {
            return "pkg:oci/$Repository@$ImageId"
        }

        return "pkg:docker/$Repository@$Tag"
    }

    return "pkg:generic/$ProjectName@source"
}

function Get-ExistingVexDocuments {
    $ExistingDocuments = @()

    foreach ($Document in $VexDocuments) {
        if (Test-Path $Document) {
            $ExistingDocuments += (Resolve-Path $Document).Path
        }
        else {
            Write-Host "VEX document not found, scan runs without it: $Document"
        }
    }

    return $ExistingDocuments
}

function Convert-ToDockerWorkPath {
    param([string]$Path)

    $FullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $FullPath.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Docker-based scans only support paths inside the repository: $Path"
    }

    $RelativePath = $FullPath.Substring($RepoRoot.Length)
    while ($RelativePath.StartsWith("\") -or $RelativePath.StartsWith("/")) {
        $RelativePath = $RelativePath.Substring(1)
    }

    return "/work/$($RelativePath -replace "\\", "/")"
}

function Invoke-LocalGrype {
    if (-not (Get-Command grype -ErrorAction SilentlyContinue)) {
        throw "Grype is not installed. Install it with 'winget install Anchore.Grype' or rerun with -UseDockerGrype."
    }

    $GrypeArgs = @(
        "sbom:$CycloneDxPath",
        "--by-cve",
        "-o", "json=$VulnerabilityJsonPath",
        "-o", "sarif=$VulnerabilitySarifPath"
    )

    foreach ($Document in (Get-ExistingVexDocuments)) {
        $GrypeArgs += @("--vex", $Document)
    }

    & grype @GrypeArgs
}

function Invoke-DockerGrype {
    $DockerCycloneDxPath = Convert-ToDockerWorkPath -Path $CycloneDxPath
    $DockerVulnerabilityJsonPath = Convert-ToDockerWorkPath -Path $VulnerabilityJsonPath
    $DockerVulnerabilitySarifPath = Convert-ToDockerWorkPath -Path $VulnerabilitySarifPath

    $GrypeArgs = @(
        "run",
        "--rm",
        "-v", "${RepoRoot}:/work",
        "-w", "/work",
        "anchore/grype:v0.111.0",
        "sbom:$DockerCycloneDxPath",
        "--by-cve",
        "-o", "json=$DockerVulnerabilityJsonPath",
        "-o", "sarif=$DockerVulnerabilitySarifPath"
    )

    foreach ($Document in (Get-ExistingVexDocuments)) {
        $GrypeArgs += @("--vex", (Convert-ToDockerWorkPath -Path $Document))
    }

    & docker @GrypeArgs
}

function New-OpenVexDraft {
    if (-not (Test-Path $VulnerabilityJsonPath)) {
        throw "Cannot create OpenVEX draft because the Grype JSON report was not generated: $VulnerabilityJsonPath"
    }

    $Report = Get-Content -Raw -Path $VulnerabilityJsonPath | ConvertFrom-Json
    $Now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $ProductId = Get-ProductId
    $Seen = @{}
    $Statements = @()

    foreach ($Match in @($Report.matches)) {
        $VulnerabilityId = $Match.vulnerability.id
        if (-not $VulnerabilityId) {
            continue
        }

        $ComponentId = $Match.artifact.purl
        if (-not $ComponentId) {
            $ComponentName = $Match.artifact.name
            $ComponentVersion = $Match.artifact.version
            $ComponentId = if ($ComponentVersion) {
                "pkg:generic/$ComponentName@$ComponentVersion"
            }
            else {
                "pkg:generic/$ComponentName"
            }
        }

        $StatementKey = "$VulnerabilityId|$ComponentId"
        if ($Seen.ContainsKey($StatementKey)) {
            continue
        }
        $Seen[$StatementKey] = $true

        $Statements += [ordered]@{
            vulnerability = [ordered]@{
                name = $VulnerabilityId
            }
            timestamp = $Now
            products = @(
                [ordered]@{
                    "@id" = $ProductId
                    subcomponents = @(
                        [ordered]@{
                            "@id" = $ComponentId
                        }
                    )
                }
            )
            status = "under_investigation"
            status_notes = "Generated from Grype results. Review impact before changing this statement to affected, fixed, or not_affected."
        }
    }

    if ($Statements.Count -eq 0) {
        if (Test-Path $VexDraftPath) {
            Remove-Item -Path $VexDraftPath
        }

        Write-Host "No vulnerabilities found; no OpenVEX draft generated."
        return
    }

    $OpenVex = [ordered]@{
        "@context" = "https://openvex.dev/ns/v0.2.0"
        "@id" = "https://example.com/station-de-recharge/vex/$ProjectName"
        author = "Station de recharge maintainers"
        role = "Document Creator"
        timestamp = $Now
        version = 1
        tooling = "Grype JSON converted by scripts/generate-sbom.ps1"
        statements = $Statements
    }

    $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText(([System.IO.Path]::GetFullPath($VexDraftPath)), ($OpenVex | ConvertTo-Json -Depth 20), $Utf8NoBom)
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

Use-HttpsCycloneDxSchema

if ($AnalyzeVulnerabilities) {
    if ($UseDockerGrype) {
        Invoke-DockerGrype
    }
    else {
        Invoke-LocalGrype
    }

    New-OpenVexDraft

    Write-Host "Vulnerability reports generated:"
    Write-Host " - $VulnerabilityJsonPath"
    Write-Host " - $VulnerabilitySarifPath"

    if (Test-Path $VexDraftPath) {
        Write-Host "OpenVEX draft generated:"
        Write-Host " - $VexDraftPath"
    }
}
