param(
    [string]$EnvPath = ".env"
)

$ErrorActionPreference = "Stop"

function Get-PreferredLocalIPv4 {
    $interfaces = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
        Where-Object {
            $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up -and
            $_.NetworkInterfaceType -in @(
                [System.Net.NetworkInformation.NetworkInterfaceType]::Wireless80211,
                [System.Net.NetworkInformation.NetworkInterfaceType]::Ethernet
            )
        } |
        Sort-Object @{
            Expression = {
                if ($_.NetworkInterfaceType -eq [System.Net.NetworkInformation.NetworkInterfaceType]::Wireless80211) { 0 } else { 1 }
            }
        }, Name

    foreach ($interface in $interfaces) {
        $properties = $interface.GetIPProperties()
        if (-not $properties.GatewayAddresses.Count) {
            continue
        }

        foreach ($address in $properties.UnicastAddresses) {
            $ip = $address.Address
            if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
                continue
            }

            $value = $ip.ToString()
            if ($value.StartsWith("127.") -or $value.StartsWith("169.254.")) {
                continue
            }

            return $value
        }
    }

    throw "Aucune adresse IPv4 Wi-Fi/Ethernet utilisable n'a ete detectee."
}

function Set-EnvValue {
    param(
        [string[]]$Lines,
        [string]$Key,
        [string]$Value
    )

    $updated = $false
    $result = foreach ($line in $Lines) {
        if ($line -match "^$([regex]::Escape($Key))=") {
            $updated = $true
            "$Key=$Value"
        } else {
            $line
        }
    }

    if (-not $updated) {
        $result += "$Key=$Value"
    }

    return $result
}

function Merge-CommaValue {
    param(
        [string]$Current,
        [string[]]$ValuesToAdd,
        [string[]]$ValuesToRemove = @()
    )

    $items = @()
    if ($Current) {
        $items = $Current.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }

    $items = $items | Where-Object { $ValuesToRemove -notcontains $_ -and $_ -notin @("http://", "https://") }
    $items += $ValuesToAdd

    return ($items | Select-Object -Unique) -join ","
}

$root = Split-Path -Parent $PSScriptRoot
$envFile = if ([System.IO.Path]::IsPathRooted($EnvPath)) { $EnvPath } else { Join-Path $root $EnvPath }

if (-not (Test-Path $envFile)) {
    throw "Fichier .env introuvable: $envFile"
}

$lines = Get-Content $envFile
$currentValues = @{}
foreach ($line in $lines) {
    if ($line -match "^([^#=]+)=(.*)$") {
        $currentValues[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$newIp = Get-PreferredLocalIPv4
$oldIp = $currentValues["LOCAL_WIFI_IP"]
$removeHosts = @()
$removeOrigins = @()
if ($oldIp -and $oldIp -ne $newIp) {
    $removeHosts += $oldIp
    $removeOrigins += "https://$oldIp", "http://$oldIp:5173", "http://$oldIp:9000"
}

$allowedHosts = Merge-CommaValue `
    -Current $currentValues["ALLOWED_HOSTS"] `
    -ValuesToAdd @("localhost", "127.0.0.1", $newIp, "backend", "django_app") `
    -ValuesToRemove $removeHosts

$corsOrigins = Merge-CommaValue `
    -Current $currentValues["CORS_ALLOWED_ORIGINS"] `
    -ValuesToAdd @(
        "https://localhost",
        "https://127.0.0.1",
        "https://$newIp",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://${newIp}:5173",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://${newIp}:9000"
    ) `
    -ValuesToRemove $removeOrigins

$lines = Set-EnvValue -Lines $lines -Key "LOCAL_WIFI_IP" -Value $newIp
$lines = Set-EnvValue -Lines $lines -Key "FRONTEND_BASE_URL" -Value "http://${newIp}:5173"
$lines = Set-EnvValue -Lines $lines -Key "ALLOWED_HOSTS" -Value $allowedHosts
$lines = Set-EnvValue -Lines $lines -Key "CORS_ALLOWED_ORIGINS" -Value $corsOrigins

Set-Content -Path $envFile -Value $lines -Encoding UTF8

Write-Host "Adresse IP locale detectee: $newIp"
Write-Host "Frontend PC/mobile: http://${newIp}:5173/"
Write-Host "Kiosk Raspberry local: http://${newIp}:9000/"
Write-Host ".env mis a jour: $envFile"
