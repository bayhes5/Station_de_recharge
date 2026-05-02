[CmdletBinding()]
param(
    [string]$VulnerabilityReport = "sbom/station-de-recharge.vulnerabilities.json",

    [string]$OpenVexDraft = "sbom/station-de-recharge.openvex.json",

    [string]$OutputPath = "sbom/station-de-recharge.vulnerability-report.md",

    [int]$Top = 30
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $VulnerabilityReport)) {
    throw "Vulnerability report not found: $VulnerabilityReport"
}

$Report = Get-Content -Raw -Path $VulnerabilityReport | ConvertFrom-Json
$Matches = @($Report.matches)
$SeverityOrder = @{
    Critical = 0
    High = 1
    Medium = 2
    Low = 3
    Negligible = 4
    Unknown = 5
}

function Get-SeverityRank {
    param([string]$Severity)

    if ($SeverityOrder.ContainsKey($Severity)) {
        return $SeverityOrder[$Severity]
    }

    return $SeverityOrder.Unknown
}

function Format-Cell {
    param($Value)

    if ($null -eq $Value -or $Value -eq "") {
        return "-"
    }

    return ($Value.ToString() -replace "\|", "\|" -replace "(`r`n|`n|`r)", " ").Trim()
}

function Get-ArtifactId {
    param($Match)

    if ($Match.artifact.purl) {
        return $Match.artifact.purl
    }

    if ($Match.artifact.version) {
        return "pkg:generic/$($Match.artifact.name)@$($Match.artifact.version)"
    }

    return "pkg:generic/$($Match.artifact.name)"
}

$VexStatusByFinding = @{}
if (Test-Path $OpenVexDraft) {
    $Vex = Get-Content -Raw -Path $OpenVexDraft | ConvertFrom-Json

    foreach ($Statement in @($Vex.statements)) {
        foreach ($Product in @($Statement.products)) {
            foreach ($Subcomponent in @($Product.subcomponents)) {
                $Key = "$($Statement.vulnerability.name)|$($Subcomponent.'@id')"
                $VexStatusByFinding[$Key] = $Statement.status
            }
        }
    }
}

$GeneratedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss 'UTC'")
$SeverityCounts = $Matches |
    Group-Object { $_.vulnerability.severity } |
    ForEach-Object {
        [pscustomobject]@{
            Severity = if ($_.Name) { $_.Name } else { "Unknown" }
            Count = $_.Count
        }
    } |
    Sort-Object { Get-SeverityRank $_.Severity }

$FixStateCounts = $Matches |
    Group-Object { if ($_.vulnerability.fix.state) { $_.vulnerability.fix.state } else { "unknown" } } |
    Sort-Object Count -Descending

$TopPackages = $Matches |
    Group-Object { "$($_.artifact.name)@$($_.artifact.version)" } |
    Sort-Object Count -Descending |
    Select-Object -First 15

$PrioritizedMatches = $Matches |
    Sort-Object `
        @{ Expression = { Get-SeverityRank $_.vulnerability.severity }; Ascending = $true },
        @{ Expression = { $_.vulnerability.risk }; Ascending = $false },
        @{ Expression = { $_.vulnerability.id }; Ascending = $true } |
    Select-Object -First $Top

$Lines = [System.Collections.Generic.List[string]]::new()
$Lines.Add("# Vulnerability Report")
$Lines.Add("")
$Lines.Add("Generated: $GeneratedAt")
$Lines.Add("")
$Lines.Add("Source: ``$VulnerabilityReport``")
if (Test-Path $OpenVexDraft) {
    $Lines.Add("VEX draft: ``$OpenVexDraft``")
}
$Lines.Add("")
$Lines.Add("## Summary")
$Lines.Add("")
$Lines.Add("| Severity | Findings |")
$Lines.Add("| --- | ---: |")
foreach ($Item in $SeverityCounts) {
    $Lines.Add("| $(Format-Cell $Item.Severity) | $($Item.Count) |")
}
$Lines.Add("| Total | $($Matches.Count) |")
$Lines.Add("")

$Lines.Add("## Fix States")
$Lines.Add("")
$Lines.Add("| Fix state | Findings |")
$Lines.Add("| --- | ---: |")
foreach ($Item in $FixStateCounts) {
    $Lines.Add("| $(Format-Cell $Item.Name) | $($Item.Count) |")
}
$Lines.Add("")

if ($VexStatusByFinding.Count -gt 0) {
    $VexStatusCounts = $VexStatusByFinding.Values |
        Group-Object |
        Sort-Object Count -Descending

    $Lines.Add("## VEX Status")
    $Lines.Add("")
    $Lines.Add("| Status | Statements |")
    $Lines.Add("| --- | ---: |")
    foreach ($Item in $VexStatusCounts) {
        $Lines.Add("| $(Format-Cell $Item.Name) | $($Item.Count) |")
    }
    $Lines.Add("")
}

$Lines.Add("## Most Affected Packages")
$Lines.Add("")
$Lines.Add("| Package | Findings |")
$Lines.Add("| --- | ---: |")
foreach ($Package in $TopPackages) {
    $Lines.Add("| $(Format-Cell $Package.Name) | $($Package.Count) |")
}
$Lines.Add("")

$Lines.Add("## Prioritized Findings")
$Lines.Add("")
$Lines.Add("| Severity | Risk | Vulnerability | Package | Version | Fix | VEX |")
$Lines.Add("| --- | ---: | --- | --- | --- | --- | --- |")
foreach ($Match in $PrioritizedMatches) {
    $VulnerabilityId = $Match.vulnerability.id
    $ArtifactId = Get-ArtifactId -Match $Match
    $VexKey = "$VulnerabilityId|$ArtifactId"
    $VexStatus = if ($VexStatusByFinding.ContainsKey($VexKey)) { $VexStatusByFinding[$VexKey] } else { "-" }
    $FixState = if ($Match.vulnerability.fix.state) { $Match.vulnerability.fix.state } else { "unknown" }
    $Risk = if ($null -ne $Match.vulnerability.risk) { "{0:N2}" -f [double]$Match.vulnerability.risk } else { "-" }
    $VulnerabilityLink = if ($Match.vulnerability.dataSource) {
        "[$VulnerabilityId]($($Match.vulnerability.dataSource))"
    }
    else {
        $VulnerabilityId
    }

    $Lines.Add("| $(Format-Cell $Match.vulnerability.severity) | $Risk | $(Format-Cell $VulnerabilityLink) | $(Format-Cell $Match.artifact.name) | $(Format-Cell $Match.artifact.version) | $(Format-Cell $FixState) | $(Format-Cell $VexStatus) |")
}

$Lines.Add("")
$Lines.Add("## Recommended Reading Order")
$Lines.Add("")
$Lines.Add('1. Start with Critical and High findings that have a fix state other than `wont-fix`.')
$Lines.Add("2. Review application dependencies before base-image operating system packages.")
$Lines.Add('3. Promote VEX statements from `under_investigation` only after checking whether the vulnerable code path is reachable.')

$OutputDirectory = Split-Path -Parent $OutputPath
if ($OutputDirectory) {
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText(([System.IO.Path]::GetFullPath($OutputPath)), ($Lines -join [Environment]::NewLine), $Utf8NoBom)

Write-Host "Vulnerability report generated:"
Write-Host " - $OutputPath"
