# Installs FSS Invoice Tool as a 24/7 live server (Windows Scheduled Task at startup).
# Run: Right-click -> Run with PowerShell (Admin recommended for firewall + task)

$ErrorActionPreference = "Stop"
$AppName = "FSS Invoice Tool Live"
$ToolDir = $PSScriptRoot
$RunLive = Join-Path $ToolDir "run_live.py"
$LogDir = Join-Path $ToolDir "logs"
$LogFile = Join-Path $LogDir "live-server.log"

Write-Host ""
Write-Host "=== FSS Invoice Tool — Go Live Setup ===" -ForegroundColor Cyan
Write-Host ""

# Python
$python = $null
$pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pyCmd) { $python = $pyCmd.Source }
if (-not $python) {
    Write-Host "Python not found. Install Python 3 from python.org first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Python: $python"

# Waitress
Write-Host "Installing production server (waitress)..."
& $python -m pip install waitress -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Scheduled task — runs at every user logon (server PC should auto-login or stay logged in)
$taskName = $AppName
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "`"$RunLive`"" `
    -WorkingDirectory $ToolDir

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "FSS Invoice & Accounts — live web server on port 5000" `
    -RunLevel Highest | Out-Null

Write-Host "Scheduled task '$taskName' created (starts at Windows logon)." -ForegroundColor Green

# Firewall (needs admin)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    $ruleName = "FSS Invoice Tool (port 5000)"
    netsh advfirewall firewall delete rule name="$ruleName" 2>$null | Out-Null
    netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow protocol=TCP localport=5000 profile=private,domain | Out-Null
    Write-Host "Firewall rule added for port 5000 (office network)." -ForegroundColor Green
} else {
    Write-Host "Tip: Re-run as Administrator to open firewall automatically," -ForegroundColor Yellow
    Write-Host "     or run 'Allow on Network (Run as Admin).bat'" -ForegroundColor Yellow
}

# Show team URL
Write-Host ""
Write-Host "Team URL (same office Wi-Fi / LAN):" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    ForEach-Object { Write-Host "  http://$($_.IPAddress):5000" -ForegroundColor White }

Write-Host ""
Write-Host "Start live server now?" -ForegroundColor Cyan
$start = Read-Host "(Y/N)"
if ($start -match '^(y|yes)$') {
    Start-Process -FilePath $python -ArgumentList "`"$RunLive`"" -WorkingDirectory $ToolDir -WindowStyle Normal
    Write-Host "Live server started in a new window." -ForegroundColor Green
}

Write-Host ""
Write-Host "For INTERNET access (work from home): run 'Go Live - Internet (Cloudflare).bat'" -ForegroundColor Cyan
Write-Host "Done." -ForegroundColor Green
Read-Host "Press Enter to close"
