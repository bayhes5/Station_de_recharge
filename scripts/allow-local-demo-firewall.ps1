param(
    [int[]]$Ports = @(5173, 9000, 8000, 3000, 8025, 80, 443)
)

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Ce script doit etre lance dans PowerShell en mode administrateur."
}

foreach ($port in $Ports) {
    $ruleName = "Station Recharge Demo TCP $port"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        Set-NetFirewallRule -DisplayName $ruleName -Enabled True -Action Allow -Profile Any
        continue
    }

    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $port `
        -Profile Any | Out-Null
}

Write-Host "Regles pare-feu activees pour les ports: $($Ports -join ', ')"
