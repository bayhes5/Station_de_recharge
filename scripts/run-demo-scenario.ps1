param(
    [string]$Reference = "DEMOQR1",
    [int]$Emplacement = 1,
    [int]$TelemetryCount = 5,
    [string]$Scenario = "normal",
    [string]$BackendBaseUrl = "http://localhost:8000/api",
    [string]$KioskBaseUrl = "http://localhost:9000",
    [switch]$SkipDockerStart
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Invoke-DockerBackendCommand {
    param([string[]]$Arguments)
    $output = & docker compose exec -T backend python manage.py @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Commande Django echouee: python manage.py $($Arguments -join ' ')"
    }
    return ($output -join "`n")
}

function Convert-JsonCommandOutput {
    param([string]$RawOutput)
    try {
        return ($RawOutput | ConvertFrom-Json)
    } catch {
        # Some commands may print harmless lines before the JSON payload.
    }

    $lines = $RawOutput -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    for ($index = $lines.Count - 1; $index -ge 0; $index--) {
        try {
            return ($lines[$index] | ConvertFrom-Json)
        } catch {
            continue
        }
    }
    throw "Aucune ligne JSON valide dans la sortie: $RawOutput"
}

function Invoke-JsonPost {
    param(
        [string]$Uri,
        [object]$Body,
        [hashtable]$Headers = @{}
    )
    $json = $Body | ConvertTo-Json -Depth 12
    return Invoke-RestMethod -Method Post -Uri $Uri -ContentType "application/json" -Headers $Headers -Body $json
}

function Invoke-JsonGet {
    param(
        [string]$Uri,
        [hashtable]$Headers = @{}
    )
    return Invoke-RestMethod -Method Get -Uri $Uri -Headers $Headers
}

if (-not $SkipDockerStart) {
    Write-Step "Demarrage des services de demonstration"
    & docker compose up -d db redis mqtt backend celery mqtt-bridge grafana raspberry
    if ($LASTEXITCODE -ne 0) {
        throw "Impossible de demarrer la stack Docker."
    }
}

Write-Step "Preparation de la reservation QR"
$prepareRaw = Invoke-DockerBackendCommand @(
    "prepare_demo_qr_reservation",
    "--reference", $Reference,
    "--emplacement", "$Emplacement"
)
$prepared = Convert-JsonCommandOutput $prepareRaw
$terminal = $prepared.terminal
$reservation = $prepared.reservation
$user = $prepared.user

Write-Host "Reservation: $($reservation.reference_code)"
Write-Host "Utilisateur: $($user.pseudo) / $($user.password)"
Write-Host "Station: $($terminal.station) / Borne: $($terminal.borne) / Emplacement: $($terminal.emplacement)"
Write-Host "Slot MQTT: $($terminal.slot_id)"
Write-Host "Prefix MQTT: $($terminal.mqtt_prefix)"

Write-Step "Creation de la session mobile cote kiosk"
$mobileSessionResponse = Invoke-JsonPost `
    -Uri "$KioskBaseUrl/backend-api/terminal/mobile-sessions/" `
    -Body @{
        station_id = $terminal.station_id
        borne_id = $terminal.borne_id
    }
$mobileToken = $mobileSessionResponse.mobile_session.token
Write-Host "Token session mobile: $mobileToken"

Write-Step "Connexion mobile utilisateur"
$loginResponse = Invoke-JsonPost `
    -Uri "$BackendBaseUrl/login/" `
    -Body @{
        identifiant = $user.pseudo
        password = $user.password
    }
$authHeaders = @{ Authorization = "Bearer $($loginResponse.access)" }
Write-Host "Connexion OK pour $($loginResponse.user.pseudo)"

Write-Step "Lecture des reservations compatibles mobile"
$mobileDetail = Invoke-JsonGet -Uri "$BackendBaseUrl/mobile-sessions/$mobileToken/" -Headers $authHeaders
$selectedReservation = $mobileDetail.reservations | Where-Object {
    $_.id -eq $reservation.id -or $_.reference_code -eq $reservation.reference_code
} | Select-Object -First 1

if (-not $selectedReservation) {
    throw "Reservation $($reservation.reference_code) absente de la session mobile."
}
if (-not $selectedReservation.compatible_terminal) {
    throw "Reservation trouvee mais incompatible avec cette station/borne."
}
Write-Host "Reservation compatible: $($selectedReservation.reference_code)"

Write-Step "Autorisation depuis le mobile"
$authorizeResponse = Invoke-JsonPost `
    -Uri "$BackendBaseUrl/mobile-sessions/$mobileToken/authorize/" `
    -Headers $authHeaders `
    -Body @{ reservation_id = $reservation.id }
Write-Host "Statut mobile: $($authorizeResponse.mobile_session.status)"

Write-Step "Consommation de l'autorisation par le kiosk"
$consumeResponse = Invoke-JsonPost `
    -Uri "$KioskBaseUrl/backend-api/terminal/mobile-sessions/consume/" `
    -Body @{
        token = $mobileToken
        station_id = $terminal.station_id
        borne_id = $terminal.borne_id
    }
$session = $consumeResponse.session
Write-Host "Session backend: $($session.id)"
Write-Host "Ecran attendu: Recharger a l'emplacement $($session.emplacement)"

Write-Step "Commande START vers le slot MQTT"
$startResponse = Invoke-JsonPost `
    -Uri "$KioskBaseUrl/mqtt/command" `
    -Body @{
        action = "START"
        slot_id = $session.slot_id
        session_id = $session.id
        station = $session.station
        borne = $session.borne
        emplacement = $session.emplacement
    }
Write-Host "START MQTT: topic=$($startResponse.mqtt.topic), ack=$($startResponse.mqtt.ack_received)"

Write-Step "Simulation de telemetrie uniquement sur la session active"
Invoke-DockerBackendCommand @(
    "simulate_mqtt_telemetry",
    "--reservation-code", $reservation.reference_code,
    "--scenario", $Scenario,
    "--interval", "1",
    "--count", "$TelemetryCount"
) | Write-Host
Start-Sleep -Seconds 3

Write-Step "Commande STOP et cloture de session"
$stopMqttResponse = Invoke-JsonPost `
    -Uri "$KioskBaseUrl/mqtt/command" `
    -Body @{
        action = "STOP"
        slot_id = $session.slot_id
        session_id = $session.id
        station = $session.station
        borne = $session.borne
        emplacement = $session.emplacement
    }
Write-Host "STOP MQTT: topic=$($stopMqttResponse.mqtt.topic), ack=$($stopMqttResponse.mqtt.ack_received)"

$stopResponse = Invoke-JsonPost `
    -Uri "$KioskBaseUrl/backend-api/terminal/sessions/stop/" `
    -Body @{
        session_id = $session.id
        station_id = $terminal.station_id
        borne_id = $terminal.borne_id
    }
Write-Host "Session cloturee: $($stopResponse.session.status)"

Write-Step "Etat final backend et Grafana"
$stateRaw = Invoke-DockerBackendCommand @(
    "print_demo_scenario_state",
    "--reference", $reservation.reference_code
)
$state = Convert-JsonCommandOutput $stateRaw
$state | ConvertTo-Json -Depth 12

Write-Host ""
Write-Host "Demo terminee." -ForegroundColor Green
Write-Host "Grafana: http://localhost:3000"
Write-Host "Kiosk:   $KioskBaseUrl/?station_id=$($terminal.station_id)&borne_id=$($terminal.borne_id)"
