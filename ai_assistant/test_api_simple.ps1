# Simple test of the ERP AI Assistant API
# Usage: ./test_api_simple.ps1

param(
    [string]$Question = "Qui sont mes clients ?",
    [string]$Addr = "localhost",
    [int]$Port = 8000
)

$url = "http://$Addr`:$Port/assistant/query"
$body = @{question=$Question} | ConvertTo-Json -Compress

Write-Host ""
Write-Host "Testing: $Question" -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Gray
Write-Host ""

try {
    $response = Invoke-WebRequest `
        -Uri $url `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -UseBasicParsing `
        -ErrorAction Stop
    
    Write-Host "Status: $($response.StatusCode)" -ForegroundColor Green
    
    # Parse response
    if ($response.Content) {
        $result = $response.Content | ConvertFrom-Json
        
        Write-Host ""
        Write-Host "Intent:      $($result.intent)" -ForegroundColor Yellow
        Write-Host "Domain:      $($result.domain)" -ForegroundColor Yellow
        Write-Host "Confidence:  $($result.confidence)" -ForegroundColor Yellow
        
        if ($result.selected_endpoint) {
            Write-Host ""
            Write-Host "Selected Endpoint: $($result.selected_endpoint.id)" -ForegroundColor Magenta
        }
        
        Write-Host ""
        Write-Host "Answer:" -ForegroundColor Green
        Write-Host $result.answer
        
        if ($result.filtered_result.count -gt 0) {
            Write-Host ""
            Write-Host "Found $($result.filtered_result.count) records" -ForegroundColor Cyan
        }
        
        if ($result.errors.Count -gt 0) {
            Write-Host ""
            Write-Host "Errors:" -ForegroundColor Red
            $result.errors | ForEach-Object { Write-Host "  • $_" }
        }
    }
    else {
        Write-Host "Empty response" -ForegroundColor Red
    }
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Is server running?"
    Write-Host "   python ai_assistant/main.py --serve"
    Write-Host ""
    Write-Host "2. Is Ollama running?"
    Write-Host "   ollama serve"
    Write-Host "" 
    Write-Host "3. Check endpoints config:"
    Write-Host "   Get-Content ai_assistant/data/endpoints.sample.json"
}

Write-Host ""
