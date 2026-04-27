# Test the ERP AI Assistant API

param(
    [string]$Question = "Qui sont mes clients ?",
    [string]$Hostname = "localhost",
    [int]$Port = 8000,
    [switch]$Raw
)

$url = "http://$Hostname`:$Port/assistant/query"
$body = @{question=$Question} | ConvertTo-Json

Write-Host "Testing ERP AI Assistant" -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Gray
Write-Host "Question: $Question" -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri $url `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -UseBasicParsing `
        -ErrorAction Stop
    
    $result = $response.Content | ConvertFrom-Json
    
    if ($Raw) {
        Write-Host "Raw JSON:" -ForegroundColor Cyan
        Write-Host ($result | ConvertTo-Json -Depth 10)
        return
    }
    
    # Parse and display response
    Write-Host "Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Classification:" -ForegroundColor Cyan
    Write-Host "  Intent: $($result.intent)"
    Write-Host "  Domain: $($result.domain)"
    Write-Host ""
    
    if ($result.selected_endpoint) {
        Write-Host "Selected Endpoint:" -ForegroundColor Cyan
        Write-Host "  ID: $($result.selected_endpoint.id)"
        Write-Host "  URL: $($result.selected_endpoint.url)"
        Write-Host ""
    }
    
    Write-Host "Result:" -ForegroundColor Cyan
    Write-Host "  Records Found: $($result.filtered_result.count)"
    Write-Host "  Total Count: $($result.filtered_result.total_count)"
    Write-Host "  Confidence: $($result.confidence)"
    Write-Host ""
    
    Write-Host "Answer:" -ForegroundColor Green
    Write-Host $result.answer
    Write-Host ""
    
    if ($result.errors -and $result.errors.Count -gt 0) {
        Write-Host "Errors:" -ForegroundColor Red
        foreach ($error in $result.errors) {
            Write-Host "  - $error"
        }
    }
    else {
        Write-Host "No errors" -ForegroundColor Green
    }
}
catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Is the server running? python ai_assistant/main.py --serve"
    Write-Host "2. Is Ollama running? ollama serve"
    Write-Host "3. Check endpoint config" -ForegroundColor Gray
}
