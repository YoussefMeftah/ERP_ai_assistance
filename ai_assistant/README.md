# ERP AI Assistant - Modular LangGraph Implementation

A production-grade AI assistant for ERP systems using **LangGraph**, **Ollama (DeepSeek + Llama)**, and intelligent endpoint routing.

## Project Structure

```
ai_assistant/
├── main.py                          # Entry point (HTTP server + CLI)
├── state.py                         # AssistantState TypedDict definition
├── config.py                        # Environment configuration & defaults
├── nodes/                           # Graph node implementations
│   ├── __init__.py
│   ├── classify_question.py         # Intent & domain classification
│   ├── retrieve_candidates.py       # Endpoint loading & semantic scoring
│   ├── endpoint_scoring.py          # Scoring logic (extracted for reuse)
│   ├── select_endpoint.py           # DeepSeek routing + score-based fallback
│   ├── call_webapi.py               # HTTP API execution + caching
│   ├── evidence_filter.py           # Result filtering + MongoDB staging + Llama filtering
│   ├── answer_generation.py         # Llama-based answer generation
│   └── answer_validation.py         # Confidence adjustment
├── utils/                           # Shared utilities
│   ├── __init__.py
│   ├── api_client.py                # Ollama & HTTP clients
│   ├── text_utils.py                # Text processing, tokenization, domain inference
│   ├── endpoint_loader.py           # Swagger/JSON/override endpoint loading
│   ├── data_processing.py           # Filtering, normalization, evidence building
│   └── mongodb_staging.py           # MongoDB integration for large results
└── data/
    ├── endpoints.sample.json        # Static endpoint definitions
    ├── endpoint_overrides.json      # ID -> URL mapping overrides
    └── cache/                       # Cached API results
```

## Key Features

### 1. **Modular Node Architecture**
- Each graph node in its own file  
- Clear input/output contracts via `AssistantState`
- Independent unit testing possible

### 2. **Dual LLM Routing**
- **DeepSeek (endpoint router)**: Intelligently selects which API to call
- **Llama (answer generator)**: Converts raw data into human-friendly responses
- **Fallback mechanism**: Score-based selection if LLM unavailable

### 3. **Advanced Filtering**
- Limit results to 20 records for evidence
- **MongoDB staging** for large result sets (>50 records)
- **Llama-based client-side filtering** for custom conditions ("sales > 100 TND")

### 4. **Flexible Endpoint Discovery**
- Load from Swagger API (live endpoint discovery)
- Load from static JSON config (`endpoints.sample.json`)
- Apply URL overrides (`endpoint_overrides.json`)
- Automatic domain classification

## Quick Start

### 1. Install & Activate Environment

```powershell
cd aierplanggraph
.\.venv\Scripts\Activate.ps1
```

### 2. Run in CLI Mode

```powershell
# Default question
python ai_assistant/main.py

# Custom question
python ai_assistant/main.py --question "Combien de clients j'ai à Paris ?"


```

### 3. Run as HTTP Server

```powershell
# Default: localhost:8000
python ai_assistant/main.py --serve

# Custom host/port
python ai_assistant/main.py --serve --host 0.0.0.0 --port 9000
```

### 4. Make API Requests

```bash
curl -X POST http://localhost:8000/assistant/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels sont mes clients de Paris ?"}'
```

## Configuration

All configuration is environment variable-based. See `config.py` for defaults.

### Essential Variables

```powershell
# ERP API
$env:ERP_API_BASE_URL = "https://localhost:44393"
$env:ERP_API_BEARER_TOKEN = "your_jwt_token"

# Endpoint loading
$env:ERP_ENDPOINT_SOURCE = "swagger"  # or "file"
$env:ERP_ENDPOINTS_JSON = "path/to/endpoints.json"
$env:ERP_ENDPOINT_OVERRIDES_JSON = "path/to/overrides.json"
$env:ERP_LOAD_SWAGGER_ENDPOINTS = "1"

# LLM Models
$env:OLLAMA_URL = "http://localhost:11434/api/chat"
$env:OLLAMA_MODEL_ROUTER = "deepseek-coder:6.7b"
$env:OLLAMA_MODEL_ANSWER = "llama3.2:latest"
$env:OLLAMA_TIMEOUT_SECONDS = "180"

# MongoDB (optional, for large result sets)
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DB_NAME = "erp_assistant_staging"
$env:MONGODB_STAGING_THRESHOLD = "50"

# HTTP Server
$env:ERP_ASSISTANT_HOST = "127.0.0.1"
$env:ERP_ASSISTANT_PORT = "8000"
```

## Graph Execution Flow

```
START
  ↓
[classify_question]
  • Determine intent (GET, AGGREGATE, FILTER)
  • Infer business domain (commercial, stock, finance, rh, achat, general)
  ↓
[retrieve_candidate_endpoints]
  • Load endpoints from Swagger/JSON/overrides
  • Score by semantic similarity to question
  • Return top 12 candidates
  ↓
[select_endpoint_and_params]
  • Try DeepSeek LLM routing on candidates
  • Extract parameters from question
  • Fallback to score-based selection if LLM unavailable
  ↓
[call_webapi]
  • Build URLs with extracted parameters
  • Execute HTTP requests to ERP API
  • Normalize responses (handles various formats)
  • Cache raw result to last_api_result.json
  ↓
[evidence_filter]
  • Load cached API results
  • Stage to MongoDB if > 50 records
  • Apply Llama-based client-side filtering (custom conditions)
  • Limit to 20 records for evidence
  • Calculate confidence score
  ↓
[answer_generation]
  • Build compact evidence from filtered results
  • Call Llama with system/user prompts
  • Fallback to template-based answer
  ↓
[answer_validation]
  • Adjust confidence based on answer quality
  • Check for negative indicators
  ↓
END (return complete state with answer, confidence, errors)
```

## Node Details

### classify_question
**Input**: User question  
**Output**: intent, domain

Determines what user wants and which business area it relates to.

```python
# Intent: "GET" (list), "AGGREGATE" (stats), "FILTER" (conditions)
# Domain: "commercial", "stock", "finance", "rh", "achat", "general"
```

### retrieve_candidate_endpoints
**Input**: question, intent, domain  
**Output**: endpoint_candidates (scored)

Loads endpoints and scores by semantic relevance using token overlap + business heuristics.

### select_endpoint_and_params
**Input**: endpoint_candidates, question  
**Output**: selected_endpoints, extracted_params

**DeepSeek Router Prompt**:
```
You are the primary endpoint router for an ERP API.
Choose the exact business GET endpoint that best answers the user question.
Return strict JSON: {"endpoint_ids": [...], "extracted_params": {...}}
```

**Fallback**: Score-based selection

### call_webapi
**Input**: selected_endpoints, extracted_params  
**Output**: api_result_path (cached JSON file)

Executes HTTP requests and caches results to `data/cache/last_api_result.json`.

### evidence_filter
**Input**: api_result_path, question  
**Output**: filtered_result, confidence

**New Features**:
- **MongoDB Staging**: If result > 50 records, save to temporary collection (auto-expire after 24h)
- **Llama Client-Side Filtering**: If question contains filter keywords, use Llama to generate filter logic:
  ```
  "Montre les clients avec ventes > 100 TND"
  → Llama generates: record['ventes'] > 100
  ```

### answer_generation
**Input**: filtered_result, selected_endpoints, question  
**Output**: answer

**Llama System Prompt**:
```
You are an ERP support assistant.
Answer ONLY from provided evidence.
Summarize information in a business-friendly way.
```

### answer_validation
**Input**: answer, filtered_result  
**Output**: confidence (adjusted)

Heuristics:
- Negative indicators (could not, unavailable) → confidence ≤ 0.3
- Good results (count > 0) → confidence ≥ 0.75
- No results → confidence ≤ 0.4

## Key Improvements Over Legacy `langgraph_skeleton.py`

| Feature | Before | After |
|---------|--------|-------|
| **Structure** | 1 monolithic file | Modular nodes + utils |
| **Endpoint Scoring** | Inline logic | Extracted `endpoint_scoring.py` |
| **Error Handling** | Basic try/catch | Accumulated error messages |
| **API Caching** | Local file only | File + MongoDB staging |
| **Filtering** | Basic record limiting | Llama-based client-side filtering |
| **Fallbacks** | Single fallback | Multi-level fallbacks per node |
| **Configuration** | Scattered env vars | Centralized `config.py` |
| **Testing** | Difficult (monolithic) | Easy (independent nodes) |

## Advanced Usage

### Bearer Token Authentication

If your API uses JWT Bearer tokens for authentication:

```powershell
$env:ERP_API_BEARER_TOKEN = "your_jwt_token"
python ai_assistant/main.py --serve
```

The token will be sent with each request as an `Authorization: Bearer <token>` header.

### Custom Endpoint Definition

Edit `data/endpoints.sample.json`:

```json
{
  "endpoints": [
    {
      "id": "get_clients_paris",
      "method": "GET",
      "url": "/api/Client/GetAllClients",
      "intent": "GET",
      "keywords": ["client", "clients", "paris", "liste"],
      "description": "Get all clients"
    }
  ]
}
```

### Endpoint URL Overrides

For safe corrections without modifying source, use `data/endpoint_overrides.json`:

```json
{
  "get_clients": "/api/Client/GetAllClients",
  "get_orders": "/api/Commande/GetAll"
}
```

### Enable Ollama Integration**

```powershell
$env:USE_OLLAMA = "1"
$env:OLLAMA_MODEL_ROUTER = "deepseek-coder:6.7b"
$env:OLLAMA_MODEL_ANSWER = "llama3.2:latest"
python ai_assistant/main.py --serve
```

Make sure Ollama is running:
```powershell
ollama serve
# In another terminal:
ollama pull deepseek-coder:6.7b
ollama pull llama3.2:latest
```

### Enable MongoDB Staging

```powershell
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_STAGING_THRESHOLD = "50"

# When API returns > 50 records, they're staged to MongoDB
# and available for efficient filtering/querying
```

## Logging & Debugging

```powershell
$env:DEBUG = "1"
$env:LOG_LEVEL = "DEBUG"
python ai_assistant/main.py
```

## Testing Individual Nodes

```python
from state import AssistantState
from nodes.classify_question import classify_question

state: AssistantState = {
    "question": "Quels clients de Paris en 2025 ?",
    "errors": []
}
result = classify_question(state)
print(result["intent"], result["domain"])  # AGGREGATE paris
```
