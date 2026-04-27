# ERP AI Assistant Project - Complete Architecture & Workflow Explanation

## 🎯 Project Overview

This is a **Full-Stack ERP AI Assistant** that uses LangGraph to intelligently route natural language questions to appropriate ERP API endpoints, extract parameters, call the APIs, and generate human-readable answers.

**Tech Stack:**
- **Backend AI**: Python + LangGraph (agentic workflow framework)
- **Backend API**: Java Spring Boot (ERP WebAPI)
- **Frontend**: React + Vite
- **LLM Integration**: Ollama (local models)
- **Data Processing**: Swagger API discovery, semantic matching, caching
- **Infrastructure**: Docker Compose (Airflow, orchestration)

---

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React)                            │
│  - Quick action buttons (Show Clients, Payment Stats, etc)      │
│  - Query input field                                             │
│  - Response table display                                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓ POST /assistant/query
┌─────────────────────────────────────────────────────────────────┐
│            PYTHON LANGGRAPH ASSISTANT (AI Engine)               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. classify_question    → Extract intent & domain         │  │
│  │ 2. retrieve_candidate   → Semantic scoring of endpoints   │  │
│  │ 3. select_endpoint      → Choose best endpoint(s)         │  │
│  │ 4. call_webapi          → Execute HTTP requests           │  │
│  │ 5. evidence_filter      → Format results                  │  │
│  │ 6. answer_generation    → Use Ollama LLM for natural text │  │
│  │ 7. answer_validation    → Confidence scoring              │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Endpoint Discovery:                                             │
│  ├─ endpoints.sample.json (static config)                      │
│  ├─ endpoint_overrides.json (URL mapping)                      │
│  └─ Swagger API (live endpoint discovery)                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓ GET /api/... (various endpoints)
┌─────────────────────────────────────────────────────────────────┐
│              JAVA SPRING BOOT ERP WEBAPI                        │
│  - REST endpoints for: Clients, Orders, Stock, Finance, HR     │
│  - OData filtering support                                      │
│  - Reports & statistics endpoints                              │
│  - JWT authentication                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 HOW THE SYSTEM DISCOVERS AVAILABLE APIS

### Step 1: Endpoint Configuration Sources

The system loads APIs from **three sources** (in priority order):

#### **Source A: Static Configuration (`endpoints.sample.json`)**
```json
{
  "endpoints": [
    {
      "id": "get_clients",
      "method": "GET",
      "url": "/api/clients",
      "intent": "GET",
      "keywords": ["clients", "liste", "afficher"]
    }
  ]
}
```
- **Pros**: Fast, reliable, can be version-controlled
- **Cons**: Manual maintenance required

#### **Source B: Dynamic Swagger Discovery**
```python
def _load_swagger_generated_endpoints() -> List[Dict[str, Any]]:
```
- Fetches `{BASE_URL}/swagger/v1/swagger.json` from the running Java API
- Automatically extracts all GET endpoints
- **Extracts from each endpoint:**
  - Path: `/api/Clients/GetAllClients`
  - Tags, summary, description, operation ID
  - Query & route parameters
  - Assigns unique ID: `webapi_get_api_clients_getalclients`

**Example Generated Endpoint:**
```python
{
  "id": "webapi_get_api_client_getalclients",
  "method": "GET",
  "url": "/api/Client/GetAllClients",
  "intent": "GET",  # or "AGGREGATE" if keywords contain "stats", "report", etc
  "keywords": ["client", "clients", "list"],  # Extracted from URL, summary, tags
  "routeParameters": [],
  "queryParameters": ["pageNumber", "pageSize"],
  "role": "commercial",  # Inferred from path tokens
  "tags": ["Client"],
  "description": "Get all clients from the system"
}
```

#### **Source C: Endpoint Overrides (`endpoint_overrides.json`)**
```json
{
  "get_clients": "/api/Client/GetAllClients",
  "filter_clients": "/odata/ClientOdata"
}
```
- Maps endpoint IDs to actual API paths
- Allows remapping endpoints without modifying configs
- Useful for API versioning or URL changes

### Step 2: How Keywords Are Generated

```python
def _path_to_keywords(path: str) -> List[str]:
    # Converts: "/api/StatsVente/GetReportsVentes"
    # Into: ["stats", "vente", "get", "reports", "ventes"]
    # Removes stop words: "api", "odata", "get", "v1", "swagger"
    # Returns: ["stats", "vente", "reports"]
```

**Purpose**: Enable semantic matching between user questions and APIs

### Step 3: Domain Classification

```python
def _infer_domain_from_path(path: str) -> str:
    # Routes endpoints to domains:
    # - "commercial": URLs with "client", "commande", "blclient"
    # - "stock": URLs with "depot", "article", "bonentree"
    # - "finance": URLs with "paiement", "transfert", "depense"
    # - "rh": URLs with "conge", "paie", "employe"
    # - "achat": URLs with "fournisseur", "frs"
```

**Purpose**: Filter endpoints by business domain early in the matching process

---

## 🎯 HOW THE SYSTEM KNOWS WHAT TO CALL

### The Endpoint Selection Pipeline

#### **Step 1: Classify the Question**
```python
def classify_question(state: AssistantState) -> AssistantState:
    # Determine INTENT:
    # - "AGGREGATE" if keywords: stat, top, chiffre, total, vente, rapport
    # - "FILTER" if keywords: filtre, ou, where, condition
    # - "GET" (default)
    
    # Determine DOMAIN:
    # - Keyword matching: paiement→finance, client→commercial, stock→stock
    # - Priority anchors for ambiguous cases
```

**Input**: User question
**Output**: `intent` (GET/FILTER/AGGREGATE) + `domain` (commercial/stock/finance/rh/achat/general)

#### **Step 2: Retrieve Candidate Endpoints**
```python
def retrieve_candidate_endpoints(state: AssistantState) -> AssistantState:
    endpoints = _load_endpoints()  # Load from all 3 sources
    scored = _score_endpoints(endpoints, question, intent, domain, apply_business_filter=True)
```

**Scoring Algorithm** (`_compute_endpoint_score`):

1. **Tokenize question & endpoint keywords:**
   - Question: "Affiche les clients de Paris"
   - Tokens: {affiche, clients, paris}
   - Endpoint keywords: {client, clients, list}
   - **Match score = overlapping tokens × 4**

2. **Domain matching bonus:**
   - If endpoint.role == question.domain: +1

3. **Intent matching bonus:**
   - If endpoint.intent == question.intent: +2

4. **Content-specific bonuses:**
   - "getall", "list", "odata" endpoints: +4
   - Special reports ("/api/reports/commande_client-report"): +5
   - Sales-related question + sales endpoint: +6

5. **Negative penalties:**
   - Test endpoints, auth, swagger, debug: -20

**Example:**

Question: "Montre-moi le stock des articles"
```
Scoring:
- Endpoint 1: /api/Stock/GetAllStock
  Tokens: {stock, get, all} vs {stock, articles} → 1 overlap × 4 = 4
  Domain: stock == stock → +1
  Intent: GET == GET → +2
  Content: "getall" → +4
  TOTAL = 11 ✅

- Endpoint 2: /api/Clients/GetAllClients
  Tokens: {client, clients, get} vs {stock, articles} → 0 overlap × 4 = 0
  Domain: commercial != stock → 0
  TOTAL = 0 ❌
```

**Output**: Top 5 candidates, ranked by score

#### **Step 3: Select Best Endpoint (with Optional LLM)**

```python
def select_endpoint_and_params(state: AssistantState) -> AssistantState:
    # Default: Use top 1 or top N endpoints (based on intent)
    # With Ollama: Ask LLM router to pick best endpoint
```

**Without Ollama (Fast Path):**
- Takes top 1 endpoint from candidates
- Simple regex extraction for parameters (IDs, dates)

**With Ollama (Smart Path):**
```python
system_prompt = """
You are the primary endpoint router for an ERP API.
Choose the exact business GET endpoint that best answers the user question.
Prefer endpoints like GetAll, OData list, stats, reports.
Return JSON: {endpoint_ids: [...], extracted_params: {...}}
"""

user_prompt = f"""
Question: {question}
Intent: {intent}
Candidates: [
  {id: "get_clients", url: "/api/Client/GetAllClients", role: "commercial"},
  {id: "get_articles", url: "/api/Article/GetAll", role: "stock"}
]
Pick the best endpoint_ids and extract useful parameters.
"""
```

The LLM decides which endpoint(s) to use and extracts parameters like IDs, dates, etc.

---

## 🚀 HOW APIs ARE CALLED

### Step 1: Build the Request

```python
def call_webapi(state: AssistantState) -> AssistantState:
    # Get selected endpoint(s) and parameters
    selected = state.get("selected_endpoint")
    params = state.get("extracted_params")  # E.g., {id: 123, date: "2024-01-15"}
```

### Step 2: Resolve the URL

**Template Substitution:**
```python
def _build_endpoint_url(url_template: str, params: Dict[str, Any]) -> str:
    # Template: "/api/Client/GetById/{id}"
    # Params: {id: 123}
    # Result: "/api/Client/GetById/123"
```

**Swagger Path Resolution (if needed):**
- Checks if path exists in live Swagger
- Falls back to fuzzy matching if exact path not found
- Matches by tokens and path patterns

### Step 3: Collect Request Parts

```python
# Route parameters (in URL path)
required = endpoint.get("requiredParameters")  # Must be provided in params

# Query parameters (after ?)
query_keys = endpoint.get("queryParameters")
# Add defaults: pageNumber=1, pageSize=50 (for list endpoints)
```

**Example:**
- Template: `/odata/ClientOdata?$filter=City eq 'Paris'&$top=50`
- Query params: `{$filter: "City eq 'Paris'", $top: 50}`

### Step 4: Make the HTTP Request

```python
for full_url in candidate_urls:
    try:
        response = requests.get(
            full_url,
            headers={"Authorization": f"Bearer {token}"},  # If configured
            timeout=60,
            verify=False  # Self-signed certs in dev
        )
        response.raise_for_status()
        body = response.json()
        data = _normalize_data_field(body)  # Extract "value", "items", or whole object
        
        # Success - break and use this result
        break
    except requests.RequestException as exc:
        # Try next base URL
        last_exc = exc
```

### Step 5: Normalize Response Data

```python
def _normalize_data_field(payload: Any) -> List[Any]:
    # Different APIs return data differently:
    # - OData: {"value": [...]}          → extracted: [...]
    # - Some: {"items": [...]}            → extracted: [...]
    # - Others: [direct list]             → extracted: [direct list]
    # - Single object: {...}              → extracted: [{...}]
```

### Step 6: Cache Results

```python
payload = {
  "generatedAt": "2024-04-14T10:30:00Z",
  "endpoints": ["get_clients"],
  "params": {id: 123},
  "calls": [  # HTTP call details
    {
      "endpoint": "get_clients",
      "url": "/api/clients",
      "fullUrl": "http://localhost:5000/api/Client/GetAllClients",
      "statusCode": 200,
      "dataCount": 45,
      "error": null
    }
  ],
  "data": [  # Actual response data
    {endpoint: "get_clients", record: {...}},
    {endpoint: "get_clients", record: {...}}
  ]
}

# Saved to: ai_assistant/data/cache/last_api_result.json
```

---

## 🔄 THE LANGGRAPH WORKFLOW (7-Step Pipeline)

The system is built as a **state machine** where each node processes the current state and adds/updates fields.

### Workflow Diagram

```
START
  ↓
[1] classify_question
  question → intent, domain
  ↓
[2] retrieve_candidate_endpoints
  intent, domain → endpoint_candidates (scored list)
  ↓
[3] select_endpoint_and_params
  endpoint_candidates → selected_endpoint, selected_endpoints, extracted_params
  ↓
[4] call_webapi
  selected_endpoint(s), params → HTTP calls → api_result_path (cached JSON)
  ↓
[5] evidence_filter
  api_result_path → filtered_result (records[:20], counts)
  ↓
[6] answer_generation
  filtered_result + selected_endpoint → answer (LLM-generated or fallback)
  ↓
[7] answer_validation
  answer → confidence score
  ↓
END
```

### AssistantState (Data Flow)

```python
class AssistantState(TypedDict):
    # INPUT
    question: str  # User's natural language question
    
    # PIPELINE OUTPUTS
    intent: str  # GET | FILTER | AGGREGATE
    domain: str  # commercial | stock | finance | rh | achat | general
    endpoint_candidates: List[Dict]  # Scored endpoint list
    selected_endpoints: List[Dict]  # Top N endpoints chosen
    selected_endpoint: Optional[Dict]  # Primary endpoint
    extracted_params: Dict  # Parameters extracted from question
    api_result_path: str  # Path to cached API response
    filtered_result: Dict  # Processed records
    answer: str  # Final natural language answer
    confidence: float  # 0.0-1.0
    errors: List[str]  # Error messages accumulated
```

### Node Details

#### **Node 1: classify_question**
```python
def classify_question(state: AssistantState) -> AssistantState:
    question = state["question"]  # "Quels sont mes clients de Paris ?"
    
    # Intent detection
    if any(word in question.lower() for word in ["stat", "top", "chiffre", "total", "vente"]):
        intent = "AGGREGATE"
    elif any(word in question.lower() for word in ["filtre", "ou", "where"]):
        intent = "FILTER"
    else:
        intent = "GET"
    
    # Domain detection
    domain = _infer_domain_from_question(question)
    # "clients" + "paris" → domain = "commercial"
    
    return {"intent": intent, "domain": domain}
```

#### **Node 2: retrieve_candidate_endpoints**
```python
def retrieve_candidate_endpoints(state: AssistantState) -> AssistantState:
    endpoints = _load_endpoints()  # ~50-100 endpoints from all sources
    scored = _score_endpoints(
        endpoints,
        state["question"],
        state["intent"],
        state["domain"],
        apply_business_filter=True
    )
    # Score each endpoint
    # Filter out test/auth/swagger endpoints
    # Sort by score
    # Return top 12 (if Ollama) or top 5
    
    return {"endpoint_candidates": scored[:12]}
```

#### **Node 3: select_endpoint_and_params**
```python
def select_endpoint_and_params(state: AssistantState) -> AssistantState:
    candidates = state["endpoint_candidates"]
    
    # Simple extraction (regex)
    params = _extract_simple_params(state["question"])
    # Looks for: id123, date patterns, etc in text
    
    # If Ollama available: ask LLM to pick best
    if use_ollama:
        selected_endpoints, llm_params, error = _select_best_endpoints(
            candidates, state["question"], state["intent"], use_ollama=True
        )
        params.update(llm_params)
    else:
        selected_endpoints = [candidates[0]]  # Just take top 1
    
    return {
        "selected_endpoints": selected_endpoints,
        "selected_endpoint": selected_endpoints[0] if selected_endpoints else None,
        "extracted_params": params,
        "errors": errors
    }
```

#### **Node 4: call_webapi**
```python
def call_webapi(state: AssistantState) -> AssistantState:
    # For each selected endpoint:
    # 1. Substitute route parameters: /api/{id} → /api/123
    # 2. Collect query parameters
    # 3. Resolve path from Swagger (if mismatch)
    # 4. Make HTTP GET request
    # 5. Handle response (normalize data)
    # 6. Collect errors
    
    # Save all results to: ai_assistant/data/cache/last_api_result.json
    return {"api_result_path": path, "errors": errors}
```

#### **Node 5: evidence_filter**
```python
def evidence_filter(state: AssistantState) -> AssistantState:
    # Load cached API result
    payload = json.load(cache_file)
    records = payload["data"]  # All returned records
    
    # Take first 20 records
    filtered = records[:20]
    
    # Count by endpoint
    by_endpoint = {"get_clients": 5, "get_fournisseurs": 3}
    
    # Estimate confidence
    confidence = 0.6 if filtered else 0.2
    
    return {
        "filtered_result": {
            "records": filtered,
            "count": len(filtered),
            "by_endpoint": by_endpoint
        },
        "confidence": confidence
    }
```

#### **Node 6: answer_generation**
```python
def answer_generation(state: AssistantState) -> AssistantState:
    # If Ollama running:
    system_prompt = """You are an ERP support assistant.
    Answer only from provided evidence.
    Summarize only useful information."""
    
    user_prompt = f"""
    Question: {state["question"]}
    Endpoint: {state["selected_endpoint"]["id"]}
    Evidence: {state["filtered_result"]["records"]}
    """
    
    answer = _call_ollama_chat(model, system_prompt, user_prompt)
    # Calls Ollama API (http://localhost:11434)
    # Gets natural language response
    
    # Fallback (if Ollama not running):
    # "Found 5 clients via endpoint get_clients..."
    
    return {"answer": answer}
```

#### **Node 7: answer_validation**
```python
def answer_validation(state: AssistantState) -> AssistantState:
    confidence = state["confidence"]  # Start at 0.6
    
    # Adjust based on answer quality
    if "could not" in state["answer"].lower():
        confidence = min(confidence, 0.3)
    elif state["filtered_result"]["count"] > 0:
        confidence = max(confidence, 0.75)
    
    return {"confidence": confidence}
```

---

## 🌐 HTTP API Server

The LangGraph assistant runs as an **HTTP server** accepting POST requests:

```
POST /assistant/query
Content-Type: application/json

{
  "question": "Quels sont les clients de Paris ?"
}
```

**Response:**
```json
{
  "question": "Quels sont les clients de Paris ?",
  "intent": "GET",
  "domain": "commercial",
  "endpoint_candidates": [...],
  "selected_endpoints": [...],
  "extracted_params": {},
  "api_result_path": "/path/to/cache/last_api_result.json",
  "filtered_result": {
    "records": [...],
    "count": 5
  },
  "answer": "Vous avez 5 clients à Paris...",
  "confidence": 0.75,
  "errors": []
}
```

---

## ⚙️ CONFIGURATION & ENVIRONMENT VARIABLES

### Endpoint Discovery Configuration

```bash
# Source: swagger (dynamic) or json (static)
ERP_ENDPOINT_SOURCE="swagger"  # Default: swagger

# Static endpoints file
ERP_ENDPOINTS_JSON="path/to/endpoints.json"  # Default: endpoints.sample.json

# Load Swagger endpoints in addition to static
ERP_LOAD_SWAGGER_ENDPOINTS=1  # Default: 1 (yes)

# Swagger file location (fallback if API unreachable)
ERP_SWAGGER_JSON="path/to/swagger_live.json"

# Endpoint URL overrides
ERP_ENDPOINT_OVERRIDES_JSON="path/to/endpoint_overrides.json"
```

### API Base URL Configuration

```bash
# **Option 1: Explicit URL**
ERP_API_BASE_URL="http://localhost:5000"

# **Option 2: Auto-detect from WebApi project**
ERP_WEBAPI_PROJECT_DIR="C:/path/to/WebApi"
# Reads: WebApi/Properties/launchSettings.json

# Authentication
ERP_API_BEARER_TOKEN="eyJhbGc..."  # JWT token
```

### Ollama LLM Configuration

```bash
# Enable Ollama for smart routing and answer generation
USE_OLLAMA=0  # Default: 0 (disabled)

# Ollama server URL
OLLAMA_URL="http://localhost:11434/api/chat"

# Models
OLLAMA_MODEL_ROUTER="deepseek-coder:6.7b"  # Selects endpoints
OLLAMA_MODEL_ANSWER="llama3.1:8b"  # Generates final answer

# Timeouts
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_ROUTER_TIMEOUT_SECONDS=180

# Candidate limit (how many endpoints to show LLM)
ERP_ROUTER_CANDIDATE_LIMIT=12
```

### Assistant Server Configuration

```bash
# HTTP server host & port
ERP_ASSISTANT_PORT=8000  # Default: 8000
```

---

## 🧠 DOMAIN-SPECIFIC LOGIC

### Commercial Domain (Clients, Orders, Sales)
**Keywords**: client, clients, commande, commandes, vente, facture, bl
**Typical Endpoints**:
- `/api/Client/GetAllClients` → GET all clients
- `/odata/CommandeClientOdata` → FILTER orders
- `/api/Reports/commande_client-report` → AGGREGATE sales by client

### Stock Domain
**Keywords**: stock, inventaire, depot, article, lot
**Typical Endpoints**:
- `/odata/StockOdata` → Query inventory
- `/api/B2b_intermediate/GetAllArticles` → List articles

### Finance Domain
**Keywords**: paiement, depense, transfert, solde, créance
**Typical Endpoints**:
- `/odata/PaiementClientOdata` → List payments
- `/api/Paiements/GetFactClt` → Get client invoices

### HR Domain
**Keywords**: employe, paie, congé, salaire
**Typical Endpoints**:
- `/api/DemandeConge/GetAllEmployes` → List employees
- `/odata/PaieFichesOdata` → Payroll records

### Achat (Purchasing) Domain
**Keywords**: fournisseur, achat
**Typical Endpoints**:
- `/api/Fournisseur` → Supplier list

---

## 📱 FRONTEND INTEGRATION

The React frontend includes **quick actions** that bypass manual typing:

```javascript
const QUICK_ACTIONS = [
  {
    label: 'Afficher les clients',
    query: 'affiche les clients',  // Sent to /assistant/query
  },
  {
    label: 'Statistiques ventes',
    query: 'affiche les ventes',
  }
];
```

When clicked, it POSTs to the Python backend's `/assistant/query` endpoint and displays the response in a table.

---

## 🚦 START-UP FLOW

### One-Command Startup

```powershell
# From project root:
./start_all.ps1

# Does:
# 1. Check if WebApi running (Java Spring Boot)
# 2. Start Ollama server (if USE_OLLAMA=1)
# 3. Start Python LangGraph assistant
# 4. Start React frontend (Vite dev server)
# 5. Open browser to http://localhost:5173
```

### Manual Startup

```bash
# Terminal 1: Java backend
mvn spring-boot:run  # Starts on http://localhost:5000

# Terminal 2: Python assistant
python ai_assistant/langgraph_skeleton.py --serve  # Starts on http://127.0.0.1:8000

# Terminal 3: React frontend
npm --prefix ./frontend run dev  # Starts on http://localhost:5173
```

---

## 📊 DATA FLOW EXAMPLE

**Scenario**: User asks "Show me all clients from Paris"

### Step-by-Step Execution

```
1. FRONTEND
   User types: "Affiche les clients de Paris"
   → POST http://localhost:5173:/assistant/query
   
2. CLASSIFY_QUESTION
   Input: "Affiche les clients de Paris"
   → Detect keywords: "clients" → domain = "commercial"
   → No "stat/top/vente" → intent = "GET"
   Output: intent="GET", domain="commercial"

3. RETRIEVE_CANDIDATE_ENDPOINTS
   Load endpoints (40+ total)
   Score each against ("clients", "paris"):
   - webapi_get_api_client_getalclients: score=7 ✅
   - webapi_get_api_fournisseur_...: score=0
   - webapi_get_api_stock_...: score=0
   Output: endpoint_candidates = [{score: 7, id: "get_clients", ...}]

4. SELECT_ENDPOINT_AND_PARAMS
   Input: endpoint_candidates
   Extract params (regex):
   - Looks for ID patterns, dates, etc.
   - "Paris" doesn't match ID pattern → params={}
   
   With Ollama:
   Ask LLM: "Which endpoint for 'Affiche les clients de Paris'?"
   → LLM: {endpoint_ids: ["get_clients"], extracted_params: {}}
   
   Output: selected_endpoint = {id: "get_clients", url: "/api/Client/GetAllClients", ...}

5. CALL_WEBAPI
   Build URL: /api/Client/GetAllClients
   Check overrides: GET /api/Client/GetAllClients (from endpoint_overrides.json)
   Query params: {pageNumber: 1, pageSize: 50}
   Full URL: http://localhost:5000/api/Client/GetAllClients?pageNumber=1&pageSize=50
   
   HTTP GET → Response:
   {
     "value": [
       {id: 1, name: "Client A", city: "Paris", ...},
       {id: 2, name: "Client B", city: "Paris", ...},
       ...
     ]
   }
   
   Normalize: Extract "value" array → 2 records
   
   Cache to: ai_assistant/data/cache/last_api_result.json
   Output: api_result_path = "/path/to/cache/last_api_result.json"

6. EVIDENCE_FILTER
   Load cache file
   records = [
     {endpoint: "get_clients", record: {id: 1, name: "Client A", city: "Paris"}},
     {endpoint: "get_clients", record: {id: 2, name: "Client B", city: "Paris"}},
   ]
   
   Take first 20 (already have 2)
   Count: 2 records from "get_clients"
   confidence = 0.6
   Output: filtered_result = {records: [...], count: 2}

7. ANSWER_GENERATION
   Ask Ollama:
   """
   Question: Affiche les clients de Paris
   Endpoint: get_clients
   Evidence: [
     {id: 1, name: "Client A", city: "Paris"},
     {id: 2, name: "Client B", city: "Paris"}
   ]
   
   Answer as a helpful ERP assistant.
   """
   
   Ollama Response:
   "Voici les 2 clients de Paris dans votre système:
    1. Client A - ID 1
    2. Client B - ID 2"
   
   Output: answer = "Voici les 2 clients..."

8. ANSWER_VALIDATION
   Check: "could not" in answer? No
   Check: records count > 0? Yes
   confidence = max(0.6, 0.75) = 0.75
   Output: confidence = 0.75

9. RETURN TO FRONTEND
   {
     question: "Affiche les clients de Paris",
     intent: "GET",
     domain: "commercial",
     endpoint_candidates: [...],
     selected_endpoints: [...],
     answer: "Voici les 2 clients de Paris...",
     filtered_result: {records: [...], count: 2},
     confidence: 0.75,
     errors: []
   }

10. FRONTEND DISPLAY
    - Shows answer text
    - Shows results table with 2 rows
    - Shows confidence badge (75%)
```

---

## 🎯 FUTURE IMPROVEMENTS (from TODO.md)

The project roadmap includes:

1. **Unified Endpoints file**: Merge all 3 sources into single `all_endpoints.json`
2. **Semantic Embeddings**: Use FAISS + SentenceTransformer for faster endpoint matching
3. **Vector Retrieval**: Replace heuristic scoring with semantic search
4. **Optimized Router**: Use LLM only when similarity < 0.8 (not always)
5. **Enhanced Params**: Always extract parameters via LLM post-selection
6. **LRU Caching**: Cache query embeddings for speed
7. **Airflow DAG**: Auto-refresh embeddings daily
8. **Evaluation**: Test accuracy and performance metrics

---

## 🔑 KEY FILES SUMMARY

| File | Purpose |
|------|---------|
| [langgraph_skeleton.py](ai_assistant/langgraph_skeleton.py) | Main AI engine (7-node workflow) |
| [endpoints.sample.json](ai_assistant/data/endpoints.sample.json) | Static endpoint definitions |
| [endpoint_overrides.json](ai_assistant/data/endpoint_overrides.json) | URL override mappings |
| [swagger_live.json](ai_assistant/swagger_live.json) | Cached Swagger spec (fallback) |
| [last_api_result.json](ai_assistant/data/cache/last_api_result.json) | Latest API call results |
| [App.jsx](frontend/src/App.jsx) | React UI component |
| [JavaerpApplication.java](src/main/java/erpweb/javaerp/JavaerpApplication.java) | Java Spring Boot entry |
| [pom.xml](pom.xml) | Java dependencies (Spring Boot, Spring AI) |
| [package.json](package.json) | NPM scripts for startup |
| [start_all.ps1](start_all.ps1) | One-command project startup |

