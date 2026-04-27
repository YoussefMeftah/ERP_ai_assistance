#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Refresh Swagger cache from live ERP API
.DESCRIPTION
    Fetches the latest Swagger spec from the live ERP API and caches it locally.
    Useful when your API endpoints have changed.
.PARAMETER Show
    Show the first N endpoints after refresh
.PARAMETER Count
    Number of endpoints to show (default: 10)
.EXAMPLE
    .\refresh_swagger_cache.ps1
    .\refresh_swagger_cache.ps1 -Show
    .\refresh_swagger_cache.ps1 -Show -Count 20
#>

param(
    [switch]$Show,
    [int]$Count = 10
)

$ErrorActionPreference = "Stop"

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "🔄 Refreshing Swagger Cache" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Build Python arguments
$Args = @()
if ($Show) {
    $Args += "-s", "-c", $Count
}

# Run from the ai_assistant directory
Push-Location $ScriptDir
try {
    python utils/refresh_swagger_cache.py @Args
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Swagger cache refreshed successfully!`n" -ForegroundColor Green
    } else {
        Write-Host "`n❌ Failed to refresh cache`n" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "`n❌ Error running refresh script: $_`n" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
