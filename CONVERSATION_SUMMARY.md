# LangGraph ERP AI Assistant - Development Summary

**Last Updated:** April 22, 2026  
**Status:** MongoDB + NoSQL workflow fully functional, results being returned successfully

---

## Project Overview

**Name:** LangGraph ERP AI Assistant  
**Purpose:** LLM-powered query system for ERP data using LangGraph workflow orchestration  
**Stack:** Python (Flask), LLM (Ollama/DeepSeek), ERP API (HTTPS/Bearer Token)  
**Key Framework:** LangGraph for multi-node workflows

---

## Critical Problems Solved

### 1. **Data Parsing Bug** ⭐ CRITICAL
**Problem:** API returned 886 clients but system showed only 1 record  
**Root Cause:** `normalize_data_field()` function didn't check for "data" field in response  
- API response structure: `{"message": "...", "data": [886 records]}`
- Function only checked "value" and "items" fields
- When checks failed, it wrapped entire response as single record: `[{"message": "...", "data": [...]}]`

**Solution:**
```python
# In utils/data_processing.py - normalize_data_field()
# Added check for "data" field FIRST (before "value" and "items")
if isinstance(payload, dict):
    if "data" in payload and isinstance(payload["data"], list):
        return payload["data"]
    elif "value" in payload:...
    elif "items" in payload:...
```

### 2. **Port Configuration Error**
**Problem:** Connection refused on port 5000  
**Root Cause:** ERP API runs on HTTPS port 44393, not HTTP port 5000  
**Solution:** Updated `config.py` default from `http://localhost:5000` to `https://localhost:44393`

### 3. **Data Extraction Pipeline Issues**
**Problem:** Evidence filter not extracting records from correct cache structure  
**Solution:** Fixed cache path in `evidence_filter.py` to extract from `calls[].raw.data`

### 4. **Answer Generation Only Showed Limited Count**
**Problem:** Answer said "20 clients" instead of "886 clients"  
**Root Cause:** Used `count` (limited evidence set) instead of `total_count` (actual total)  
**Solutions:**
- Updated `answer_generation.py` to use `total_count`
- Updated `build_answer_evidence()` to pass `total_count` to LLM evidence
- Default `commercialCategory` changed from 0 to 1 for StatsVente endpoints

### 5. **StatsVente Endpoints Missing Parameters**
**Problem:** StatsVente API calls failed because required parameters weren't added  
**Required Parameters:** `DateDebut`, `DateFin`, `commercialCategory=1`  
**Solution:** Hardcoded defaults in `call_webapi.py` collect_request_parts()

### 6. **Date Range Parsing**
**Problem:** System didn't understand "dans 2025" or "in 2024 and 2025"  
**Solution:** Enhanced `extract_simple_params()` in `text_utils.py`:
- "dans 2025" → "01-01-2025" to "12-31-2025"
- "in 2024 and 2025" → "01-01-2024" to "12-31-2025"
- Default (no year): current year Jan 1 to Dec 31

---

## Architecture Changes

### Data Pipeline Flow
```
ERP API (44393) 
  ↓
call_webapi.py [Extract 886 records, cache result]
  ↓
evidence_filter.py [Extract from cache, limit by intent (20/100)]
  ↓
answer_generation.py [Build evidence, call LLM, return answer]
```

### Intent-Based Record Limiting (NEW)
- **AGGREGATE/REPORT/STATS:** Show 100 records (for complete analysis)
- **GET:** Show 20 records (sufficient sample)
- **total_count:** Always calculated from all records, displayed in answer

### Debug Logging (REMOVED)
Cleaned up all `print(f"DEBUG: ...")` statements from:
- `call_webapi.py` (6 statements)
- `evidence_filter.py` (1 statement)

---

## Files Modified

| File | Changes | Impact |
|------|---------|--------|
| `config.py` | Default URL: `http://5000` → `https://44393` | API connectivity |
| `utils/data_processing.py` | Added "data" field check in `normalize_data_field()` | 886 records now extracted |
| `nodes/evidence_filter.py` | Cache extraction path, intent-based limiting, record limit logic | Correct data extraction |
| `nodes/answer_generation.py` | Use `total_count` instead of `count`, intent-aware evidence size | Accurate answer counts |
| `utils/text_utils.py` | Enhanced date parsing for year ranges | "dans 2025" works correctly |
| `nodes/call_webapi.py` | StatsVente parameter defaults added | StatsVente queries functional |
| `nodes/select_endpoint.py` | Only log error if both LLM and fallback fail | Cleaner error handling |

---

## Current System Capabilities

✅ **Working:**
- API returns full dataset (886+ records for clients)
- System extracts all records correctly
- Evidence limited by intent (20 for GET, 100 for AGGREGATE)
- Date parsing handles year ranges ("dans 2025", "in 2024 and 2025")
- StatsVente endpoints work with automatic parameters
- LLM answers show total_count correctly
- Bearer token authentication works
- Answer generation creates proper French responses

⚠️ **Known Limitations:**
- DeepSeek (router LLM) has timeout issues (180s default) - fallback works
- MongoDB staging available but not actively used for display
- Ollama must be running on localhost:11434

---

## Configuration Values

**Key Endpoints:**
- ERP API: `https://localhost:44393`
- Flask Server: `http://localhost:8000`
- Ollama: `http://localhost:11434`

**Models:**
- Answer Generation: Llama 3.1 (or configured model)
- Router: DeepSeek (endpoint selection)

**Timeouts:**
- Ollama default: 180 seconds
- Can be increased via config if needed

**StatsVente Defaults:**
- `commercialCategory`: 1 (always)
- `DateDebut`: "01-01-{current_year}" (if not specified)
- `DateFin`: "12-31-{current_year}" (if not specified)

---

## Testing

**Test Script:** `ai_assistant/test_api_simple.ps1`

```powershell
.\ai_assistant\test_api_simple.ps1 -Question "afficher les ventes par articles dans 2025"
```

**Expected Output:**
- Status: 200
- Intent: AGGREGATE
- Confidence: 0.75+
- Answer: Complete analysis of all months' sales data
- Found records: Up to 100 (for AGGREGATE)

---

## Example Queries That Now Work

1. **"Qui sont mes clients ?"** 
   - Returns all 886 clients
   - Shows total_count in answer

2. **"afficher les ventes par articles dans 2025"**
   - Dates: 01-01-2025 to 12-31-2025
   - Returns 58 sales records with monthly breakdown
   - LLM analyzes complete year

3. **"in 2024 and 2025"**
   - Dates: 01-01-2024 to 12-31-2025
   - Shows data for both years

---

## Next Steps / Known TODO Items

1. Investigate Ollama timeout issues further (timeout=300 may help)
2. Consider implementing MongoDB result caching for very large datasets (1000+)
3. Add more language support (currently French/English)
4. Optimize LLM context window usage for massive datasets
5. Add result export functionality (CSV, PDF)

---

## Development Notes

- **Python Version:** 3.14
- **Key Dependencies:** 
  - `requests` (HTTP client)
  - `langgraph` (workflow orchestration)
  - `ollama` (LLM integration)
  - `flask` (web server)

- **Authentication:** Bearer token (not NTLM despite earlier attempts)

- **Data Format:** 
  - Input: JSON from ERP API
  - Internal: Python dicts
  - Output: JSON from Flask endpoint

---

## April 22, 2026 - MongoDB + NoSQL Workflow Implementation (NEW SESSION)

### Session Summary
Completed major architectural redesign: replaced traditional 7-node pipeline with 6-node **MongoDB + NoSQL** workflow. System now uses Llama to generate MongoDB aggregation pipelines instead of traditional answer generation.

### Key Changes Implemented

#### 1. **Workflow Redesign: Traditional → MongoDB + NoSQL**

**OLD Pipeline (7 nodes):**
```
classify_question → retrieve_candidates → select_endpoint → call_webapi → 
evidence_filter → answer_generation → answer_validation → END
```

**NEW Pipeline (6 nodes):**
```
classify_question → retrieve_candidates → select_endpoint → call_webapi → 
llama_nosql_query_generator → execute_mongodb_query → format_mongodb_results → END
```

**Removed Nodes:** `evidence_filter`, `answer_generation`, `answer_validation` (replaced by MongoDB querying)

#### 2. **New Nodes Created**

**`llama_nosql_query_generator.py`**
- Receives: user question + available data fields from API results
- Calls Llama to generate valid MongoDB aggregation pipeline
- Returns: MongoDB pipeline as JSON list of stages
- Handles: JSON parsing with fallback regex fixes for unquoted keys and regex patterns
- Key feature: Tells Llama about nested `record` field structure with dot notation (`$record.fieldname`)

**`execute_mongodb_query.py`**
- Receives: MongoDB aggregation pipeline + collection name
- Connects to MongoDB and executes aggregation
- Returns: Query results (list of documents)
- Handles: ObjectId serialization for JSON output

**`format_mongodb_results.py`**
- Receives: Raw MongoDB query results
- Formats into human-readable answer text
- Includes: All result fields (including `_id` from `$group` operations)
- Returns: Formatted answer string

#### 3. **Data Flow Fixes**

**Problem 1: Nested Data Structure Not Recognized**
- API saves records with structure: `{endpoint, sourceUrl, record: {code, designation, qteVente, ...}}`
- Initial implementation only saw top-level fields: `['endpoint', 'sourceUrl', 'record']`
- Llama couldn't generate correct queries

**Solution:** Extract nested field names in `call_webapi.py`:
```python
# Check if records have nested 'record' field
if "record" in first_record and isinstance(first_record["record"], dict):
    data_headers = list(first_record["record"].keys())
```

**Problem 2: Llama Generating Invalid JSON**
- Llama returned unquoted keys: `{$match: ...}` instead of `{"$match": ...}`
- Llama returned regex patterns: `{record.code: /^[A-Z]{3,5}-\d{4}$/}` (invalid JSON)

**Solutions:**
- Updated system prompt to emphasize JSON formatting and forbid regex
- Added regex fix in JSON parser: `/pattern/` → `{"$regex": "pattern"}`
- Added unquoted key fix: `$stage:` → `"$stage":`

**Problem 3: Unnecessary $match Filters**
- Llama added `$match` filters even when question didn't ask for filtering
- Example: "afficher les ventes par articles" (show sales by articles) shouldn't filter
- Result: Empty result sets

**Solution:** Updated user prompt to explicitly explain when to use `$match`:
```
Only add $match filter if the question explicitly asks to filter by a specific value.
For example:
- 'show all articles' → NO $match, just $group
- 'show articles where code=ABC' → ADD $match with that code
```

#### 4. **Bearer Token Authentication - RESOLVED**

**Investigation:**
- Added debug logging to Bearer token handling
- Confirmed token IS being read from environment
- Confirmed token IS being sent in Authorization header
- API responded with **200 OK** ✅ (not 401)

**Conclusion:** Bearer token authentication is working correctly. Previous 401 errors were due to:
1. Token expiration (JWT tokens have exp claim)
2. Token not being set in server's environment when started

#### 5. **MongoDB Integration**

**Setup:**
- Installed: `pymongo` package
- MongoDB: Running on `mongodb://localhost:27017`
- Database: `erp_assistant_staging`
- Collection name: Generated from endpoint IDs (e.g., `webapi_get_api_statsvente_statsventepararticle`)

**Connection Pattern (Lazy Initialization):**
```python
# In mongodb_staging.py
_mongodb_staging_instance = None

def _get_mongodb_staging():
    global _mongodb_staging_instance
    if _mongodb_staging_instance is None:
        _mongodb_staging_instance = MongoDBStaging()  # Initialize on first use
    return _mongodb_staging_instance
```
- **Why?** Environment variables must be set BEFORE MongoDB connection attempt
- **Solution:** Connect lazily when first needed, not at module import time

#### 6. **Debug Logging Added (Comprehensive)**

Added detailed debug output to trace full workflow:

**1. MongoDB Data Save (`call_webapi.py`):**
```
[DEBUG] ===== MONGODB DATA SAVE =====
[DEBUG] Collection: webapi_get_api_statsvente_statsventepararticle
[DEBUG] Record count: 14
[DEBUG] Data headers: ['code', 'designation', 'qteVente', 'totalHT', 'totalTTC', 'period']
[DEBUG] First record sample: {...}
[DEBUG] ================================
```

**2. Llama Query Generation (`llama_nosql_query_generator.py`):**
```
[DEBUG] ===== LLAMA MONGODB QUERY GENERATION =====
[DEBUG] Question: afficher les ventes par articles
[DEBUG] Available fields: ['code', 'designation', 'qteVente', 'totalHT', 'totalTTC', 'period']
[DEBUG] Generated MongoDB Pipeline: [...]
[DEBUG] ==============================================
```

**3. MongoDB Execution (`execute_mongodb_query.py`):**
```
[DEBUG] ===== MONGODB QUERY EXECUTION =====
[DEBUG] Collection: webapi_get_api_statsvente_statsventepararticle
[DEBUG] Pipeline stages: 4
[DEBUG] Query returned 10 results
[DEBUG] First result sample: {...}
[DEBUG] ========================================
```

### Test Results

**Question:** "afficher les ventes par articles" (show sales by articles)

**Output:**
```
Status: 200
Intent: AGGREGATE
Domain: stock
Confidence: 0.85

Answer:
Found 10 results:

  Item/Group: UNITE CENTRAL DELL 5040 
  Totalqty: 1.00
  Totalht: 2040.00

  Item/Group: DELL 24 MONITOR
  Totalqty: 2.00
  Totalht: 1250.00

  [... 8 more results ...]
```

**What Happened:**
1. ✅ API returned 14 sales records
2. ✅ Records saved to MongoDB
3. ✅ Llama generated aggregation pipeline: `$group` by designation, sum quantities and totals
4. ✅ MongoDB executed pipeline and returned 10 results (top by totalHT)
5. ✅ Results formatted into readable answer

### Known Limitations & Future Work

1. **Ollama Model Memory:** DeepSeek-coder requires 1.5GB but only 1.1GB available
   - Currently disabled: `USE_OLLAMA=0`
   - Fallback: Score-based endpoint selection works fine
   
2. **Llama Quality:** Sometimes generates non-essential `$match` filters
   - Mitigated by improved prompt
   - Could improve with few-shot examples
   
3. **Result Formatting:** Currently simple key-value display
   - Could enhance with: tables, CSV, JSON exports

### Configuration Reference

**Start MongoDB:**
```powershell
mongod
```

**Start Server (with all required env vars):**
```powershell
$env:MONGODB_URI = "mongodb://localhost:27017"
$env:MONGODB_DB_NAME = "erp_assistant_staging"
$env:ERP_API_BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
$env:USE_OLLAMA = "0"
python ai_assistant/main.py --serve
```

**Test Query:**
```powershell
.\ai_assistant\test_api_simple.ps1 -Question "afficher les ventes par articles"
```

### Files Modified in Session

| File | Changes |
|------|---------|
| `nodes/llama_nosql_query_generator.py` | NEW - Llama query generation with JSON parsing/fixing |
| `nodes/execute_mongodb_query.py` | NEW - MongoDB aggregation pipeline execution |
| `nodes/format_mongodb_results.py` | NEW - Result formatting into readable text |
| `nodes/__init__.py` | Added imports for new nodes |
| `main.py` | Updated graph to use new 6-node pipeline |
| `state.py` | Added MongoDB fields: collection_name, data_headers, mongodb_query, query_results, result_count |
| `call_webapi.py` | Added MongoDB save logic, nested field extraction, debug logging |
| `evidence_filter.py` | Updated to use lazy MongoDB initialization |
| `utils/mongodb_staging.py` | Added lazy initialization pattern, `get_mongodb_staging()` function |

---

## Previous Session Context (April 17-20, 2026)

**Start Server:**
```powershell
cd ai_assistant
python main.py --serve
```

**Run Test:**
```powershell
.\test_api_simple.ps1 -Question "your question here"
```

**Check Python Processes:**
```powershell
Get-Process python | Where-Object {$_.CommandLine -like "*main.py*"}
```

**Kill Server:**
```powershell
Get-Process python | Where-Object {$_.CommandLine -like "*main.py*"} | Stop-Process -Force
```

---

## Key Insights

1. **Total Count Visibility:** Always show `total_count` in answers, not just `count`
2. **Intent Matters:** Use query intent to determine evidence scope (20 vs 100 records)
3. **Date Handling:** Parse year ranges naturally, not just specific dates
4. **Error Fallback:** When LLM fails, have sensible fallback behavior
5. **API Response Format:** Verify exact response structure (`data` vs `value` vs `items`)

---

**Status:** System is production-ready for basic queries. All critical bugs fixed. Ready for scale-up testing.

---

## April 23, 2026 - LLM Non-Determinism & Parameter Extraction Enhancement

### Session Overview
Addressed LLM non-determinism issues with count queries and enhanced DeepSeek endpoint router to better understand and extract required parameters from Swagger metadata.

### Problem 1: Non-Deterministic Llama Output for Count Queries

**Issue:**
Same question "Combien de clients ai-je ?" produced different MongoDB pipelines on different runs:
- **Run 1 (correct):** `[{"$group": {"_id": null, "total": {"$sum": 1}}}]` → Result: 886 ✅
- **Run 2 (broken):** `[{"$group": {"_id": "$record.cod_clt", ...}}, {"$sort": {...}}, {"$limit": 1}]` → Result: 1 ❌

**Root Cause:**
LLMs are non-deterministic by nature. Even with detailed prompts instructing simple count queries, Llama would occasionally:
- Ignore instructions and generate grouping queries instead
- Use invalid operators like `$count: {}`
- Add unnecessary stages ($sort, $limit)

**Solution: Python-Level Pre-Detection**
Implemented `_is_simple_count_query()` function that bypasses Llama entirely for deterministic queries:

```python
def _is_simple_count_query(question: str) -> bool:
    """Detect if question is asking for simple total count."""
    question_lower = question.lower()
    count_keywords = ['combien', 'how many', 'count', 'total', 'nombre de']
    unique_keywords = ['different', 'unique', 'distinct', 'différent']
    has_count = any(kw in question_lower for kw in count_keywords)
    has_unique = any(kw in question_lower for kw in unique_keywords)
    return has_count and not has_unique

# In llama_nosql_query_generator():
if _is_simple_count_query(question):
    pipeline = [{"$group": {"_id": None, "total": {"$sum": 1}}}]
    return state  # Bypass Llama completely
```

**Result:** 100% deterministic count queries, always returns 886 ✅

**Key Learning:** When dealing with LLMs, hard deterministic logic for specific patterns beats trying to make LLMs follow instructions reliably.

### Problem 2: DeepSeek Not Extracting Required Endpoint Parameters

**Issue:**
Question "donne moi les détails du clinet 4110024" (give me details for client 4110024):
- DeepSeek failed to extract `clientId: "4110024"` 
- API called without parameter → 500 Server Error
- Cascade failures: no data → no headers → no query → no results

**Root Cause:**
DeepSeek wasn't aware of each endpoint's parameter requirements (types, names, locations).

**Solution: Enhanced Parameter Information in Routing**

Updated `build_router_candidates_payload()` to provide detailed parameter metadata:

```python
# For each endpoint, now includes:
{
    "id": "webapi_get_api_blclient_getdetails",
    "url": "/api/BlClient/GetDetails/{clientId}",
    "parameters": {
        "required": [
            {
                "name": "clientId",
                "type": "string",
                "location": "path",
                "required": True,
                "description": "The client ID to retrieve",
                "example": "4110000"
            }
        ],
        "optional": [...]
    }
}
```

Enhanced system prompt to guide DeepSeek:
```
PARAMETER EXTRACTION:
- Each endpoint shows required and optional parameters with type information
- REQUIRED parameters: Must extract from question. Look for values matching the type
- Match parameter names EXACTLY as shown (case-sensitive)
- For missing required parameters, use context to infer smart defaults
- For ID parameters: extract business IDs (client codes, product codes, etc)
```

Added detailed parameter reference section in user prompt showing all endpoint requirements upfront.

**Result:** DeepSeek now sees:
1. What each endpoint does
2. What parameters it needs
3. Parameter types and descriptions
4. Example values

This should improve parameter extraction accuracy significantly.

### Problem 3: Unicode Encoding Error in HTTP Request Handling

**Issue:**
Server crashed with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9` when processing request with French characters.

**Error:** PowerShell sent request with different encoding (Windows-1252, UTF-16, or UTF-8-BOM) but server only tried UTF-8 decoding.

**Solution: Multi-Encoding Fallback in `main.py`:**
```python
for encoding in ["utf-8-sig", "utf-8", "utf-16", "cp1252"]:
    try:
        decoded_body = raw_body.decode(encoding)
        break
    except UnicodeDecodeError:
        continue

# Last resort
if decoded_body is None:
    decoded_body = raw_body.decode("utf-8", errors="replace")
```

**Result:** Server now handles requests from any client regardless of encoding ✅

### Error Cascade Explanation

When all three problems combine, you see this error chain:

1. **DeepSeek routing failed** → Fallback to score-based selection
2. **Wrong endpoint selected** (requires clientId parameter)
3. **Parameter not extracted** → API called without required param
4. **API returns 500 Server Error**
5. **No data returned** → Next node has nothing to work with
6. **No data headers provided** → Query generator can't run
7. **No MongoDB query generated** → Executor has nothing to execute
8. **User sees:** "No results found" + 4 error messages

Each error is a cascade from previous failures, not independent problems.

### Files Modified April 23

| File | Change | Impact |
|------|--------|--------|
| `nodes/llama_nosql_query_generator.py` | Added `_is_simple_count_query()` function + pre-detection logic | 100% reliable count queries |
| `nodes/select_endpoint.py` | Enhanced `build_router_candidates_payload()` with detailed parameter info | Better parameter extraction by DeepSeek |
| `nodes/select_endpoint.py` | Improved system + user prompts with parameter extraction guidance | Clearer instructions for LLM routing |
| `nodes/select_endpoint.py` | Added debug logging for DeepSeek reasoning and extracted params | Better visibility into routing decisions |
| `main.py` | Added multi-encoding fallback in HTTP request parsing | Handles Windows/Office encoding formats |

### Test Results After Changes

**Simple Count Query:**
```powershell
.\test_api_simple.ps1 -Question "Combien de clients ai-je ?"
# Output: [DEBUG] ===== SIMPLE COUNT QUERY DETECTED =====
# Answer: Total: 886 ✅ (100% consistent)
```

**Parameter Extraction:**
```powershell
.\test_api_simple.ps1 -Question "donne moi les détails du clinet 4110024"
# Note: Still fails due to wrong endpoint selection, but now has better parameter info available
```

### Key Architectural Insights

1. **Hybrid Approach Works:** Python pre-detection + LLM for complex queries
   - Pre-detection: Deterministic patterns (count, sum, totals)
   - LLM: Complex analysis, grouping, filtering

2. **Parameter Metadata is Critical:** LLMs need to see:
   - Parameter names (case-sensitive)
   - Parameter types (string, date, number)
   - Parameter location (path vs query)
   - Parameter requirements (required vs optional)
   - Example values when available

3. **Encoding is a Hidden Complexity:** Always handle multiple encodings:
   - UTF-8 (Linux/Web standard)
   - UTF-8-BOM (Windows tools)
   - UTF-16 (Windows applications)
   - CP1252 (Windows legacy)
   - Fallback to error replacement

### Next Steps

1. **Test parameter extraction** with question requiring specific client ID
2. **Monitor DeepSeek performance** now that it has parameter details
3. **Add parameter-based unit tests** to verify extraction accuracy
4. **Consider caching endpoint parameter metadata** to speed up routing

**Status:** Core count query functionality is reliable. Parameter extraction infrastructure enhanced. Ready for testing complex parameter-based queries.

