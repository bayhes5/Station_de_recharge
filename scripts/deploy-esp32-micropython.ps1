param(
    [Parameter(Mandatory = $true)]
    [string]$Port,

    [string]$SourceDir = "esp32\emplacement1",

    [string]$FirmwareVersion = "",

    [string]$RootCaPath = "",

    [string]$RootCaRemoteName = "metropole-verte-root-ca.der",

    [switch]$OpenRepl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$mpremote = Get-Command mpremote -ErrorAction SilentlyContinue
if (-not $mpremote) {
    throw "mpremote introuvable. Installe-le avec : python -m pip install mpremote"
}

$resolvedSource = Resolve-Path -Path $SourceDir
$mainPath = Join-Path -Path $resolvedSource -ChildPath "main.py"
if (-not (Test-Path -Path $mainPath)) {
    throw "Fichier main.py introuvable dans $resolvedSource"
}

function Invoke-Mpremote {
    param([string[]]$Arguments)

    & $mpremote.Source @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "mpremote a échoué: mpremote $($Arguments -join ' ')"
    }
}

Write-Host "Déploiement de main.py vers $Port"
Invoke-Mpremote -Arguments @("connect", $Port, "fs", "cp", $mainPath, ":main.py")

if ($FirmwareVersion.Trim()) {
    $versionFile = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath "station-esp32-version.txt"
    Set-Content -Path $versionFile -Value $FirmwareVersion.Trim() -Encoding ASCII -NoNewline
    try {
        Write-Host "Déploiement de version.txt ($($FirmwareVersion.Trim()))"
        Invoke-Mpremote -Arguments @("connect", $Port, "fs", "cp", $versionFile, ":version.txt")
    }
    finally {
        Remove-Item -LiteralPath $versionFile -Force -ErrorAction SilentlyContinue
    }
}

if ($RootCaPath.Trim()) {
    $resolvedCa = Resolve-Path -Path $RootCaPath
    Write-Host "Préparation du dossier certs sur l'ESP32"
    & $mpremote.Source @("connect", $Port, "fs", "mkdir", ":certs")
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Le dossier certs existe peut-être déjà. La copie du certificat continue."
    }

    Write-Host "Déploiement du certificat CA vers certs/$RootCaRemoteName"
    Invoke-Mpremote -Arguments @(
        "connect",
        $Port,
        "fs",
        "cp",
        $resolvedCa.Path,
        ":certs/$RootCaRemoteName"
    )
}

Write-Host "Redémarrage de l'ESP32"
Invoke-Mpremote -Arguments @("connect", $Port, "reset")

if ($OpenRepl) {
    Invoke-Mpremote -Arguments @("connect", $Port, "repl")
}
