# Quick Start Guide - Rebuilt LangGraph Assistant

## 1-Minute Setup

### Activate Environment
```powershell
cd aierplanggraph
.\.venv\Scripts\Activate.ps1
```

### Set Environment Variables
```powershell
$env:ERP_API_BASE_URL = "https://localhost:44393"
$env:OLLAMA_MODEL_ROUTER = "deepseek-coder:6.7b"
$env:OLLAMA_MODEL_ANSWER = "llama3.2:latest"
```

### Start HTTP Server
```powershell
python ai_assistant/main.py --serve
```

### Test It

**Option 1: Use provided test script (Easiest)**
```powershell
powershell -ExecutionPolicy Bypass .\ai_assistant\test_api_simple.ps1

# Or custom question
powershell -ExecutionPolicy Bypass .\ai_assistant\test_api_simple.ps1 -Question "Combien de clients ai-je ?"
```

**Option 2: Manual PowerShell (Windows)**
```powershell
$body = @{question="Qui sont mes clients ?"} | ConvertTo-Json
$response = Invoke-WebRequest -Uri "http://localhost:8000/assistant/query" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -UseBasicParsing

$result = $response.Content | ConvertFrom-Json
Write-Host "Intent: $($result.intent)"
Write-Host "Domain: $($result.domain)"
Write-Host "Confidence: $($result.confidence)"
Write-Host "Answer: $($result.answer)"
```

**Option 3: Bash/Linux/macOS**
```bash
curl -X POST http://localhost:8000/assistant/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Qui sont mes clients ?"}' | jq "."
```

**⏱️ Important Timing Note:**
- **First query**: 30-60 seconds (Ollama loads LLM models into GPU memory)
- **Subsequent queries**: 5-10 seconds (models stay cached)
- If timeout occurs: `Invoke-WebRequest ... -TimeoutSec 120` or adjust `OLLAMA_TIMEOUT_SECONDS` in `config.py`

---

## CLI Mode (No Server)

```powershell
# Default question
python ai_assistant/main.py

# Custom question
python ai_assistant/main.py --question "Combien de ventes en 2025 ?"
```

---

## Configuration Checklist

- [ ] `ERP_API_BASE_URL` set (e.g., https://localhost:44393)
- [ ] `ERP_API_BEARER_TOKEN` set (if API requires auth)
- [ ] `OLLAMA_MODEL_ROUTER` set (deepseek-coder:6.7b)
- [ ] `OLLAMA_MODEL_ANSWER` set (llama3.2:latest)
- [ ] Ollama running: `ollama serve`
- [ ] ERP WebAPI running on `ERP_API_BASE_URL`
- [ ] A few test endpoints in `data/endpoints.sample.json`

---

## Response Format

```json
{
  "question": "Quels clients à Paris ?",
  "intent": "GET",
  "domain": "commercial",
  "answer": "J'ai trouvé 5 clients à Paris...",
  "confidence": 0.85,
  "selected_endpoint": {
    "id": "webapi_get_api_client_getalclients",
    "url": "/api/Client/GetAllClients"
  },
  "filtered_result": {
    "count": 5,
    "records": [...]
  },
  "errors": []
}
```

---

## Troubleshooting

### Ollama not responding
```powershell
# Check if running
ollama list

# Pull models if missing
ollama pull deepseek-coder:6.7b
ollama pull llama3.2:latest

# Start if not running
ollama serve
```

### ERP API not found
```powershell
# Test connectivity
(Invoke-WebRequest -Uri "https://localhost:44393/swagger/v1/swagger.json" -SkipCertificateCheck).StatusCode

# Check base URL
echo $env:ERP_API_BASE_URL
```

### Graph execution fails
```powershell
# Check for missing endpoints config
cat ai_assistant/data/endpoints.sample.json

# Enable debug logging
$env:DEBUG = "1"
python ai_assistant/main.py
```

---

## Files Structure

```
ai_assistant/
├── main.py ..................... Start here (HTTP server + CLI)
├── state.py .................... State contracts
├── config.py ................... Environment config
├── nodes/ ...................... 7 independent nodes
├── utils/ ...................... Shared utilities
└── README.md ................... Full documentation
```

---

## Key Commands

| Command | Purpose |
|---------|---------|
| `python main.py` | CLI: Run once with default question |
| `python main.py --serve` | Start HTTP server (port 8000) |
| `python main.py --help` | Show all options |
| `python -c "from main import build_graph; print('OK')"` | Verify build |

---

## Next Actions

1. **Configure endpoints**: Edit `data/endpoints.sample.json`
2. **Set auth**: Add `ERP_API_BEARER_TOKEN` if needed
3. **Test endpoints**: Make sure ERP WebAPI is accessible
4. **Run a question**: `python main.py --question "..."`
5. **Start server**: `python main.py --serve`
6. **Integrate with frontend**: POST to `/assistant/query`

---

## Performance Tips

- Default: 12 endpoint candidates (adjust in config)
- Reduce if no timeout: `ERP_ROUTER_CANDIDATE_LIMIT=6`
- Faster Llama model: `OLLAMA_MODEL_ANSWER=llama2:7b`
- MongoDB staging: `MONGODB_URI=mongodb://localhost:27017`

---

**For complete documentation, see [README.md](./README.md) and [REBUILD_SUMMARY.md](./REBUILD_SUMMARY.md)**
