# Endpoint Selection Test Script

## Overview

`test_endpoint_selection.py` is a **standalone test script** that isolates and tests the endpoint selection logic using **DeepSeek Coder**.

It performs 3 main tasks:
1. ✅ **Candidate Scoring** - Keyword-based baseline scoring
2. ✅ **Parameter Extraction** - DeepSeek extracts parameters from user input
3. ✅ **Endpoint Selection** - DeepSeek chooses the best endpoint based on parameters

## What It Does

```
User Question
    ↓
Load Available Endpoints (from Swagger)
    ↓
Score Candidates (keyword matching)
    ↓
[DeepSeek #1] Extract Parameters
    ├─ Analyzes question
    ├─ Identifies needed parameters
    └─ Returns: {param: value, type, confidence}
    ↓
[DeepSeek #2] Select Best Endpoint
    ├─ Considers question + extracted params
    ├─ Scores against all candidates
    └─ Returns: endpoint_id, confidence, reasoning
    ↓
Display Results with Confidence & Alternatives
```

## Usage

### Option 1: Python (Direct)

```bash
cd ai_assistant

# Basic test
python test_endpoint_selection.py "Afficher les ventes par articles"

# More examples
python test_endpoint_selection.py "Combien de clients avons-nous?"
python test_endpoint_selection.py "Show clients from Paris"
python test_endpoint_selection.py "List all products"
```

### Option 2: PowerShell (Wrapper)

```powershell
cd ai_assistant

# Basic test
.\test_endpoint_selection.ps1 -Question "Afficher les ventes par articles"

# With verbose output
.\test_endpoint_selection.ps1 -Question "Combien de clients?" -Verbose
```

## Output Example

```
======================================================================
🧪 ENDPOINT SELECTION TEST
======================================================================

📌 Question: Afficher les ventes par articles

🔄 Loading endpoints...
✅ Loaded 45 endpoints

======================================================================
🔹 CANDIDATE SCORING (Baseline - Keyword Match)
======================================================================
Intent: AGGREGATE
Domain: stock

🏆 Top Candidates (by keyword score):
   1. webapi_get_api_statsvente_statsventeparticle (score: 0.95)
      Affiche les ventes groupées par article/produit...
   2. webapi_get_api_statsvente_statsvente (score: 0.87)
      Affiche les ventes totales...
   3. webapi_get_api_commandeclient_getallclients (score: 0.42)
      Liste de tous les clients...

======================================================================
🔹 PARAMETER EXTRACTION (DeepSeek Coder)
======================================================================
❓ Question: Afficher les ventes par articles

📤 Calling DeepSeek...

✅ Extracted Parameters:
   • DateDebut: '01-01-2026' (high confidence)
     → Inferred as current year start date (default)
   • DateFin: '12-31-2026' (high confidence)
     → Inferred as current year end date (default)

📝 Summary: Standard date range for sales analysis query

======================================================================
🔹 ENDPOINT SELECTION (DeepSeek Coder)
======================================================================
❓ Question: Afficher les ventes par articles
📊 Candidates: 8 endpoints
🔍 Extracted Parameters: 2

📤 Calling DeepSeek...

✅ Selected Endpoint: webapi_get_api_statsvente_statsventeparticle
   Confidence: 98%
   Parameter Fit: high
   Reasoning: Endpoint specifically designed for sales by article with 
              date range parameters matching extracted values

🔄 Alternatives:
   • webapi_get_api_statsvente_statsvente: 87% - Could work but returns 
     total instead of per-article
   • webapi_get_api_commandeclient_getallclients: 15% - Wrong intent 
     (clients, not sales)

======================================================================
🔹 FINAL RESULT
======================================================================

✨ Selected Endpoint: webapi_get_api_statsvente_statsventeparticle
   Confidence: 98%

📦 Parameters to Use:
   • DateDebut = '01-01-2026' (string)
   • DateFin = '12-31-2026' (string)

======================================================================
```

## Test Cases

Try these different questions to see how the script handles various scenarios:

### Sales Analysis
```powershell
python test_endpoint_selection.py "Afficher les ventes par articles"
python test_endpoint_selection.py "Montrer les ventes par client"
python test_endpoint_selection.py "Show sales for January 2025"
python test_endpoint_selection.py "Sales report from March to May 2024"
```

### Client Queries
```powershell
python test_endpoint_selection.py "Combien de clients avons-nous?"
python test_endpoint_selection.py "List all clients"
python test_endpoint_selection.py "Show clients from Paris"
python test_endpoint_selection.py "Get client details for code ABC123"
```

### Aggregation Queries
```powershell
python test_endpoint_selection.py "Total revenue this year"
python test_endpoint_selection.py "How many different products?"
python test_endpoint_selection.py "Average sales per client"
```

### Edge Cases
```powershell
python test_endpoint_selection.py "xyz abc invalid query"
python test_endpoint_selection.py "a"
python test_endpoint_selection.py "Tell me everything"
```

## What Gets Tested

### DeepSeek Abilities
- ✅ **Parameter Extraction**: Can it find dates, IDs, codes in natural language?
- ✅ **Type Detection**: Does it correctly identify string vs integer vs date params?
- ✅ **Confidence Scoring**: Are confidence scores realistic?
- ✅ **Endpoint Matching**: Does it select the right endpoint?
- ✅ **Multi-language**: Works with French and English questions
- ✅ **Default Values**: Can it infer defaults when params not explicit?

### Baseline Scoring (Keyword Match)
- ✅ Does simple keyword matching work?
- ✅ How much better is DeepSeek vs baseline?

## Debugging

### See detailed output
```powershell
python test_endpoint_selection.py "Your question" 2>&1 | Tee-Object debug.log
```

### Check DeepSeek is running
```powershell
curl http://localhost:11434/api/tags
```

### Check Swagger is loaded
```powershell
python utils/refresh_swagger_cache.py -s -c 3
```

## Troubleshooting

### Error: "No module named 'ollama'"
```bash
pip install ollama requests
```

### Error: "Connection refused to Ollama"
Make sure Ollama is running:
```bash
ollama serve
```

### Error: "deepseek-coder model not found"
Download the model:
```bash
ollama pull deepseek-coder:6.7b
```

### DeepSeek returns invalid JSON
- Try a simpler question first
- Check the logs for JSON parsing errors
- May need to increase Ollama timeout

## Integration with Main Flow

This test script helps validate:
- `nodes/select_endpoint_and_params.py` - The actual selection node
- `utils/api_client.py` - DeepSeek JSON response parsing
- `utils/endpoint_loader.py` - Endpoint loading from Swagger

Once you're satisfied with results, the same logic runs automatically in the full assistant flow.

## Performance Metrics

The script shows:
- **Confidence Score**: How sure DeepSeek is (0-100%)
- **Parameter Fit**: How well extracted params match endpoint needs
- **Reasoning**: Why this endpoint was chosen
- **Alternatives**: What else could have worked

Higher confidence = more reliable endpoint selection.
