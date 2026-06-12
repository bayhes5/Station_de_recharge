param(
    [Parameter(Mandatory = $true)]
    [string]$PhoneIp,
    [string]$ScrcpyDir = ".codex_tmp\scrcpy\scrcpy-win64-v4.0",
    [int]$Port = 5555,
    [int]$MaxSize = 1080,
    [int]$MaxFps = 30
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$scrcpyPath = Join-Path $root "$ScrcpyDir\scrcpy.exe"
$adbPath = Join-Path $root "$ScrcpyDir\adb.exe"

if (-not (Test-Path $scrcpyPath) -or -not (Test-Path $adbPath)) {
    throw "scrcpy n'est pas installe dans $ScrcpyDir. Telecharge d'abord la release officielle Genymobile."
}

& $adbPath start-server | Out-Null
& $adbPath tcpip $Port
Start-Sleep -Seconds 2
& $adbPath connect "${PhoneIp}:$Port"
& $adbPath devices -l

& $scrcpyPath `
    --serial "${PhoneIp}:$Port" `
    --max-size $MaxSize `
    --max-fps $MaxFps `
    --no-audio `
    --window-title "Samsung A26 - Demo mobile"
