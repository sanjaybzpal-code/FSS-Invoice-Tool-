# Builds a ZIP package to send to your client (no passwords, no invoice data).
# Output: ..\FSS-Invoice-Tool-Client-Package.zip

$ErrorActionPreference = "Stop"
$ToolDir = $PSScriptRoot
$Parent = Split-Path $ToolDir -Parent
$ZipName = "FSS-Invoice-Tool-Client-Package.zip"
$ZipPath = Join-Path $Parent $ZipName
$Staging = Join-Path $env:TEMP "FSS-Invoice-Tool-Client-$(Get-Date -Format 'yyyyMMddHHmmss')"

Write-Host ""
Write-Host "Building client package..." -ForegroundColor Cyan

if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Path $Staging | Out-Null
$Dest = Join-Path $Staging "FSS Invoice Tool"
New-Item -ItemType Directory -Path $Dest | Out-Null

# Copy project (exclude private / generated data)
$excludeDirs = @('.git', 'Invoices', 'Exports', 'temp_imports', 'logs', '__pycache__', '.cursor')
$excludeFiles = @('auth.json', '.secret_key', 'clients_cache.json', 'invoices_log.json', 'config.json')

Get-ChildItem $ToolDir -Force | ForEach-Object {
    if ($_.PSIsContainer) {
        if ($excludeDirs -contains $_.Name) { return }
        Copy-Item $_.FullName -Destination (Join-Path $Dest $_.Name) -Recurse -Force
    } else {
        if ($excludeFiles -contains $_.Name) { return }
        if ($_.Extension -eq '.pyc') { return }
        Copy-Item $_.FullName -Destination (Join-Path $Dest $_.Name) -Force
    }
}

# Client config from example (not your live config)
Copy-Item (Join-Path $ToolDir "config.json.example") (Join-Path $Dest "config.json") -Force

# Empty Invoices folder
New-Item -ItemType Directory -Path (Join-Path $Dest "Invoices") | Out-Null
"Client invoice PDFs/Excel will be saved here." | Out-File (Join-Path $Dest "Invoices\README.txt")

# Remove nested __pycache__
Get-ChildItem $Dest -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $Dest -DestinationPath $ZipPath -CompressionLevel Optimal

Remove-Item $Staging -Recurse -Force

$sizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "Package: $ZipPath" -ForegroundColor White
Write-Host "Size:    $sizeMB MB" -ForegroundColor White
Write-Host ""
Write-Host "Send this ZIP to your client with CLIENT_SETUP.md instructions inside." -ForegroundColor Cyan
Write-Host "Or share GitHub: https://github.com/sanjaybzpal-code/FSS-Invoice-Tool-" -ForegroundColor Cyan
Write-Host ""

# Open folder
explorer.exe "/select,$ZipPath"
