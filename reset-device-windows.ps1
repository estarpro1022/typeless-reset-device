<#
.SYNOPSIS
    Reset Typeless device identifier on Windows.
    This makes Typeless treat the current machine as a new device,
    freeing up a device slot on your account.

.DESCRIPTION
    1. Kills Typeless if running
    2. Deletes device identifier from Windows Credential Manager
    3. Deletes device.cache file
    4. Deletes encrypted login state (user-data.json)
    5. Clears login state from app-storage.json
    6. Restarts Typeless

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File reset-device-windows.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "[reset-device] Typeless device identifier reset tool (Windows)" -ForegroundColor Cyan

# 1. Kill Typeless if running
$proc = Get-Process -Name "Typeless" -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "[reset-device] Stopping Typeless..."
    Stop-Process -Name "Typeless" -Force
    Start-Sleep -Seconds 2
    $still = Get-Process -Name "Typeless" -ErrorAction SilentlyContinue
    if ($still) {
        Write-Host "[reset-device] WARNING: Typeless is still running, waiting..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }
    Write-Host "[reset-device] Typeless stopped"
} else {
    Write-Host "[reset-device] Typeless is not running"
}

# 2. Delete device identifier from Credential Manager
Write-Host "[reset-device] Removing device identifier from Credential Manager..."
try {
    $output = cmdkey /delete:Typeless.deviceIdentifier 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[reset-device] Device identifier removed" -ForegroundColor Green
    } else {
        Write-Host "[reset-device] Device identifier not found in Credential Manager (already clean)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[reset-device] Device identifier not found (already clean)" -ForegroundColor Yellow
}

# 3. Delete device.cache
$deviceCache = Join-Path $env:APPDATA "Typeless\Cache\device.cache"
if (Test-Path $deviceCache) {
    Remove-Item $deviceCache -Force
    Write-Host "[reset-device] Removed device.cache" -ForegroundColor Green
} else {
    Write-Host "[reset-device] device.cache not found (already clean)" -ForegroundColor Yellow
}

# 4. Delete user-data.json (encrypted login state)
$userDataDir = Join-Path $env:APPDATA "Typeless.exe"
$userDataJson = Join-Path $userDataDir "user-data.json"
if (Test-Path $userDataJson) {
    Remove-Item $userDataJson -Force
    Write-Host "[reset-device] Removed user-data.json" -ForegroundColor Green
} else {
    Write-Host "[reset-device] user-data.json not found (already clean)" -ForegroundColor Yellow
}

# 5. Clear login state from app-storage.json (keep other settings)
$appStorage = Join-Path $userDataDir "app-storage.json"
if (Test-Path $appStorage) {
    try {
        $data = Get-Content $appStorage -Raw -Encoding UTF8 | ConvertFrom-Json
        $data.PSObject.Properties.Remove('userData')
        $data.PSObject.Properties.Remove('quotaUsage')
        $data | ConvertTo-Json -Depth 10 | Set-Content $appStorage -Encoding UTF8
        Write-Host "[reset-device] Cleared login state from app-storage.json" -ForegroundColor Green
    } catch {
        Write-Host "[reset-device] Could not clean app-storage.json: $_" -ForegroundColor Yellow
    }
}

# 6. Restart Typeless
$exePath = Join-Path $env:LOCALAPPDATA "Programs\Typeless\Typeless.exe"
if (Test-Path $exePath) {
    Write-Host "[reset-device] Starting Typeless..."
    Start-Process $exePath
    Write-Host "[reset-device] Typeless started" -ForegroundColor Green
} else {
    Write-Host "[reset-device] Typeless.exe not found at $exePath, please start it manually" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[reset-device] Done! Typeless will generate a new device identifier on next login." -ForegroundColor Cyan
Write-Host "[reset-device] You'll need to log in again in the Typeless app." -ForegroundColor Cyan
