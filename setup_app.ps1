# Installs "FSS Invoice Tool" as a launchable app:
#  - Desktop shortcut
#  - Start Menu entry
#  - (optional) auto-start when Windows starts
# Re-run anytime; it just refreshes the shortcuts.

$ErrorActionPreference = "Stop"
$AppName = "FSS Invoice Tool"
$ToolDir = $PSScriptRoot
$Launcher = Join-Path $ToolDir "launch.pyw"
$IconPath = Join-Path $ToolDir "assets\app_icon.ico"

Write-Host ""
Write-Host "Installing $AppName ..." -ForegroundColor Cyan
Write-Host "Folder: $ToolDir"

# --- Locate pythonw.exe (runs without a console window) ---
$pythonw = $null
$pyCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($pyCmd) { $pythonw = $pyCmd.Source }
if (-not $pythonw) {
    $pyExe = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pyExe) {
        $candidate = Join-Path (Split-Path $pyExe.Source) "pythonw.exe"
        if (Test-Path $candidate) { $pythonw = $candidate }
    }
}
if (-not $pythonw) {
    Write-Host "Could not find pythonw.exe. Please install Python 3 from python.org and re-run." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Using: $pythonw"

function New-AppShortcut {
    param([string]$Path)
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($Path)
    $sc.TargetPath = $pythonw
    $sc.Arguments = '"' + $Launcher + '"'
    $sc.WorkingDirectory = $ToolDir
    $sc.WindowStyle = 7
    $sc.Description = "FSS Invoice Generator"
    if (Test-Path $IconPath) { $sc.IconLocation = $IconPath }
    $sc.Save()
}

# --- Desktop shortcut ---
$desktop = [Environment]::GetFolderPath("Desktop")
New-AppShortcut -Path (Join-Path $desktop "$AppName.lnk")
Write-Host "Created Desktop shortcut." -ForegroundColor Green

# --- Start Menu shortcut ---
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "$AppName.lnk"
New-AppShortcut -Path $startMenu
Write-Host "Created Start Menu shortcut." -ForegroundColor Green

# --- Optional auto-start at login ---
$startupDir = [Environment]::GetFolderPath("Startup")
$startupLnk = Join-Path $startupDir "$AppName.lnk"
Write-Host ""
$answer = Read-Host "Start $AppName automatically when Windows starts? (Y/N)"
if ($answer -match '^(y|yes)$') {
    New-AppShortcut -Path $startupLnk
    Write-Host "Auto-start enabled." -ForegroundColor Green
} else {
    if (Test-Path $startupLnk) { Remove-Item $startupLnk -Force }
    Write-Host "Auto-start not enabled." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! Open '$AppName' from your Desktop or Start Menu." -ForegroundColor Cyan
Read-Host "Press Enter to close"
