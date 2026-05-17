param(
    [string]$ConfigDir = "mosquitto/config"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$targetDir = Join-Path $repoRoot $ConfigDir
$passwordFile = Join-Path $targetDir "passwords"

if (-not (Test-Path -LiteralPath $targetDir)) {
    throw "Dossier Mosquitto introuvable: $targetDir"
}

$accounts = @(
    "station_backend",
    "raspberry_kiosk",
    "esp32_slot1",
    "esp32_slot2",
    "esp32_slot3",
    "esp32_station_demo_borne_1_slot1",
    "esp32_station_demo_borne_1_slot2",
    "esp32_station_demo_borne_1_slot3"
)

if (Test-Path -LiteralPath $passwordFile) {
    Remove-Item -LiteralPath $passwordFile
}

foreach ($index in 0..($accounts.Count - 1)) {
    $account = $accounts[$index]
    $password = Read-Host "Mot de passe MQTT pour $account" -AsSecureString
    $passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
    try {
        if ([string]::IsNullOrWhiteSpace($plainPassword)) {
            throw "Mot de passe vide refusé pour $account."
        }

        if ($index -eq 0) {
            docker run --rm -v "${targetDir}:/mosquitto/config" eclipse-mosquitto:2 `
                mosquitto_passwd -b -c /mosquitto/config/passwords $account $plainPassword
        } else {
            docker run --rm -v "${targetDir}:/mosquitto/config" eclipse-mosquitto:2 `
                mosquitto_passwd -b /mosquitto/config/passwords $account $plainPassword
        }
    } finally {
        $plainPassword = $null
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
    }
}

Write-Host "Fichier MQTT créé: $passwordFile"
Write-Host "Pour activer le mode sécurisé, utilisez mosquitto.secure.conf comme configuration Mosquitto."
