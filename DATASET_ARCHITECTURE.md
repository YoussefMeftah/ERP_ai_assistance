# Dataset Architecture

This document describes the three datasets and how they're used in the LangSmith evaluation workflow.

## Overview

The project uses **3 separate JSON files** that serve different purposes:

```
aierplanggraph/
├── api_test.json                    # Source of Truth: API Specification
├── api_test_prompts.json            # Test Prompt Dataset (45 prompts)
└── api_test_evaluation.json         # Evaluation Dataset (45 cases with expected outputs)
ai_assistant/
└── langsmith_evaluation.py          # Loads from api_test_evaluation.json
```

---

## 1. **api_test.json** - Source of Truth (OpenAPI Specification)

**Purpose**: Single source of truth for all API endpoints and their specifications.

**Location**: `aierplanggraph/api_test.json`

**Structure**:
```json
{
  "openapi": "3.0.1",
  "info": {...},
  "paths": {
    "/api/StatsVente/StatsVente": {
      "get": {
        "parameters": [
          {"name": "DateDebut", "in": "query", ...},
          {"name": "DateFin", "in": "query", ...},
          ...
        ],
        "responses": {...}
      }
    },
    ...
  },
  "components": {...}
}
```

**Content**:
- Full OpenAPI 3.0.1 specification
- 9 Endpoints with detailed parameter definitions
- Response schemas and components
- **NO test cases** (removed)

**Endpoints Defined**:
1. `/api/StatsVente/StatsVente` - Sales statistics (DateDebut, DateFin, commercialCategory)
2. `/api/StatsVente/StatsAchats` - Purchase statistics (DateDebut, DateFin, commercialCategory)
3. `/api/StatsVente/StatsPaiements` - Payment statistics (DateDebut, DateFin, IsFrs, paiementCategory)
4. `/api/StockDepot/GetAllFamille` - Product families (no parameters)
5. `/api/StockDepot/GetAllFamilleP` - Product families variant (no parameters)
6. `/api/StockDepot/GetDepot` - Depot information (no parameters)
7. `/odata/StockLotOdata` - Stock lots (cod_dep, num_lot, etat, cod_art, desg_art)
8. `/odata/ArticleOdata` - Articles OData (cod_clt)
9. `/api/BlClient/GetById` - Client order (num_bl_clt)

**Usage**:
- Reference for endpoint definitions
- Can be used in RAG systems to provide context about available endpoints
- Updated when API changes

---

## 2. **api_test_prompts.json** - Test Prompt Dataset

**Purpose**: Collection of 5 test prompts for each endpoint. Used for prompt engineering, LLM fine-tuning, and prompt generation testing.

**Location**: `aierplanggraph/api_test_prompts.json`

**Structure**:
```json
{
  "description": "Test prompts dataset - 5 prompts for each endpoint...",
  "prompts": [
    {
      "endpoint": "/api/StatsVente/StatsVente",
      "domain": "commercial",
      "intent": "AGGREGATE",
      "parameter_keys": ["DateDebut", "DateFin", "commercialCategory"],
      "prompts": [
        "Afficher les ventes du 01/01/2024 au 31/12/2024",
        "Show me sales statistics for the entire year 2024",
        ...
      ]
    },
    ...
  ]
}
```

**Content**:
- 9 endpoint groups
- 5 prompts per endpoint (45 total)
- Mix of French and English prompts
- Mix of formal and casual language
- Mix of specific dates and generic time references

**Usage Examples**:
- Testing prompt variations for the same endpoint
- Generating synthetic training data
- A/B testing different prompt wordings
- Fine-tuning language models

**Example Use Case**:
```python
import json
from pathlib import Path

prompts_file = Path("api_test_prompts.json")
with open(prompts_file) as f:
    data = json.load(f)

# Get all prompts for StatsVente
for prompt_group in data["prompts"]:
    if prompt_group["endpoint"] == "/api/StatsVente/StatsVente":
        print(prompt_group["prompts"])
```

---

## 3. **api_test_evaluation.json** - Evaluation Dataset

**Purpose**: Paired natural language prompts with expected outputs. Used for LangSmith evaluation to measure endpoint selection accuracy and parameter extraction quality.

**Location**: `aierplanggraph/api_test_evaluation.json`

**Structure**:
```json
{
  "description": "Evaluation dataset - Natural language prompts paired with expected outputs...",
  "evaluation_cases": [
    {
      "prompt": "Afficher les ventes du 01/01/2024 au 31/12/2024",
      "expected": {
        "endpoint": "/api/StatsVente/StatsVente",
        "extracted_params": {
          "DateDebut": "2024-01-01",
          "DateFin": "2024-12-31"
        },
        "intent": "AGGREGATE",
        "domain": "commercial"
      }
    },
    ...
  ]
}
```

**Content**:
- 45 evaluation cases (5 per endpoint)
- Each case maps a prompt to expected output
- Expected output includes:
  - `endpoint`: The correct endpoint path
  - `extracted_params`: Expected parameter values (with type conversion)
  - `intent`: Classification (GET, AGGREGATE, FILTER)
  - `domain`: Business domain (commercial, stock, achat, finance)

**Usage in LangSmith**:
- Loaded by `langsmith_evaluation.py` for dataset creation
- Converted to LangSmith dataset examples
- Used to evaluate:
  - **Endpoint Exact Match Evaluator**: Did the model select the correct endpoint?
  - **Parameter Extraction Evaluator**: Were parameters extracted correctly?
  - **Intent Classification Evaluator**: Was the intent correctly classified?
  - **Domain Classification Evaluator**: Was the domain correctly identified?

---

## Data Flow Diagram

```
api_test.json (Source of Truth)
    ↓
    ├─→ api_test_prompts.json (derived for prompt engineering)
    │   └─→ Used for: LLM testing, fine-tuning, prompt variations
    │
    └─→ api_test_evaluation.json (derived with expected outputs)
        └─→ langsmith_evaluation.py
            └─→ LangSmith Dataset
                └─→ Evaluation with 4 custom evaluators
                    └─→ Metrics: accuracy, precision, extraction quality
```

---

## How LangSmith Uses api_test_evaluation.json

### Step 1: Load Dataset
```python
from langsmith_evaluation import TEST_CASES, create_or_update_dataset

# TEST_CASES loaded from api_test_evaluation.json
# Each case: {"input": {"question": prompt}, "expected_output": {...}}
```

### Step 2: Create LangSmith Dataset
```python
dataset = create_or_update_dataset()
# Creates examples in LangSmith from TEST_CASES
```

### Step 3: Run Inference
```python
# For each prompt, graph extracts:
# - endpoint: selected endpoint path
# - extracted_params: parameter values
# - intent: classified intent
# - domain: classified domain
```

### Step 4: Evaluate Against Expected
```python
# Compare predictions vs expected values using:
# 1. EndpointExactMatchEvaluator (binary: 1.0 or 0.0)
# 2. ParameterExtractionEvaluator (fuzzy: 0.0-1.0)
# 3. IntentClassificationEvaluator (binary: 1.0 or 0.0)
# 4. DomainClassificationEvaluator (binary: 1.0 or 0.0)
```

### Step 5: Generate Report
```
Results:
  Endpoint Exact Match: 0.87 (87% accurate endpoint selection)
  Parameter Extraction: 0.84 (84% parameter accuracy)
  Intent Classification: 0.92 (92% intent accuracy)
  Domain Classification: 0.89 (89% domain accuracy)
  
  Failed Cases:
  - Prompt: "Show sales data Q1"
    Expected: /api/StatsVente/StatsVente
    Predicted: /api/StatsVente/StatsAchats
```

---

## Key Differences from Old Approach

| Aspect | Old (Single File) | New (Three Files) |
|--------|-------------------|-------------------|
| api_test.json | OpenAPI spec + 9 test cases mixed | OpenAPI spec only (pure) |
| Test Prompts | Hardcoded in Python | Organized in api_test_prompts.json |
| Evaluation Cases | Embedded in api_test.json | Separate api_test_evaluation.json |
| Maintainability | Hard to update prompts | Easy: edit JSON files |
| Reusability | Limited to LangSmith | Prompts usable for any system |
| Scalability | Single file gets large | Modular, easy to extend |

---

## Maintenance Guidelines

### Adding New Prompts
1. Edit `api_test_prompts.json`
2. Add 5 new prompts under an endpoint
3. No code changes needed

### Adding New Evaluation Cases
1. Edit `api_test_evaluation.json`
2. Add prompt + expected output pair
3. Rerun `langsmith_evaluation.py --dataset-only`

### Updating API Specification
1. Edit `api_test.json` paths/parameters
2. Update corresponding prompts in `api_test_prompts.json`
3. Update evaluation cases in `api_test_evaluation.json`
4. Rerun evaluations

### Syncing Data Quality
- Prompts in `api_test_prompts.json` should relate to endpoints in `api_test.json`
- Expected values in `api_test_evaluation.json` must match endpoint definitions in `api_test.json`
- Use validation script to ensure consistency (see below)

---

## Validation Script

```python
#!/usr/bin/env python3
"""Validate consistency across the three datasets"""

import json
from pathlib import Path

api_test = json.load(open("api_test.json"))
prompts = json.load(open("api_test_prompts.json"))
evaluation = json.load(open("api_test_evaluation.json"))

# Get all endpoints from api_test.json
endpoints_in_spec = set(api_test["paths"].keys())

# Check prompts
endpoints_in_prompts = set(p["endpoint"] for p in prompts["prompts"])
assert endpoints_in_prompts == endpoints_in_spec, "Prompt endpoints don't match spec"

# Check evaluation
endpoints_in_eval = set(e["expected"]["endpoint"] for e in evaluation["evaluation_cases"])
assert endpoints_in_eval == endpoints_in_spec, "Evaluation endpoints don't match spec"

print("✅ All datasets are consistent!")
```

---

## Usage Commands

```bash
# Create/update LangSmith dataset from evaluation cases
python langsmith_evaluation.py --dataset-only

# Run quick evaluation (first 3 cases)
python langsmith_example.py --quick

# Run full evaluation with report
python langsmith_example.py --full --report
```

---

## Summary

- **api_test.json**: Pure API specification (single source of truth)
- **api_test_prompts.json**: Test prompts for each endpoint (prompt engineering)
- **api_test_evaluation.json**: Prompts + expected outputs (LangSmith evaluation)

This modular approach allows:
- ✅ Easy maintenance and updates
- ✅ Reusable prompts for multiple systems
- ✅ Clear separation of concerns
- ✅ Scalability as more endpoints/prompts are added
