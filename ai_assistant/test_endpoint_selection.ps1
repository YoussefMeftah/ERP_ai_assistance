#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test endpoint selection and parameter extraction with DeepSeek
.DESCRIPTION
    Standalone test script that:
    1. Scores endpoints by keyword match
    2. Uses DeepSeek to extract parameters from user input
    3. Uses DeepSeek to select the best endpoint
    4. Shows confidence scores and reasoning
.PARAMETER Question
    The user question to test (required)
.PARAMETER Verbose
    Show detailed output
.EXAMPLE
    .\test_endpoint_selection.ps1 -Question "Afficher les ventes par articles"
    .\test_endpoint_selection.ps1 -Question "Combien de clients?" -Verbose
.NOTES
    Requires: Ollama with deepseek-coder model running
    Location: Run from ai_assistant directory
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Question,
    
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "🧪 ENDPOINT SELECTION TEST" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "❓ Question: $Question`n" -ForegroundColor Yellow

# Run the Python script
$args = @($Question)
if ($Verbose) {
    $args += "-v"
}

python test_endpoint_selection.py @args

$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Host "`n❌ Test failed with exit code $exitCode" -ForegroundColor Red
}

exit $exitCode
