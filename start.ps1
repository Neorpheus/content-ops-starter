# Implant Safety Agent Workspace Startup Script

$Port = 8000

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Starting Implant Safety Agent Workspace" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Stop existing Flask processes on this port
$ExistingServer = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*app.py*" }
if ($ExistingServer) {
    Write-Host "[*] Stopping existing Flask server..." -ForegroundColor Yellow
    Stop-Process -Id $ExistingServer.Id -Force
}

# 2. Start Flask Server in the background
Write-Host "[*] Launching Flask server on port $Port..." -ForegroundColor Yellow
Start-Process python -ArgumentList "app.py" -WindowStyle Hidden -WorkingDirectory $PSScriptRoot

# Give it a second to bind
Start-Sleep -Seconds 2

# 3. Open default browser
Write-Host "[+] Launching clinical dashboard..." -ForegroundColor Green
Start-Process "http://127.0.0.1:$Port"

Write-Host "=========================================" -ForegroundColor Green
Write-Host "  Workspace is active! Close this window" -ForegroundColor Green
Write-Host "  to keep the server running in background." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
