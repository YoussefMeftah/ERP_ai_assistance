# Quick Reference Guide - Three Dataset Architecture

## File Purposes

```
aierplanggraph/
├── api_test.json                      # 📋 API SPEC (Source of Truth)
│                                      # Pure OpenAPI 3.0.1 definition
│                                      # Used for: RAG context, API docs
│
├── api_test_prompts.json              # 🎯 TEST PROMPTS (45 prompts)
│                                      # 5 prompts per endpoint
│                                      # Used for: Prompt engineering, fine-tuning
│
├── api_test_evaluation.json           # ✅ EVALUATION DATASET (45 cases)
│                                      # Prompt → Expected output pairs
│                                      # Used for: LangSmith evaluation
│
└── ai_assistant/
    ├── langsmith_evaluation.py        # Loads from api_test_evaluation.json
    ├── langsmith_example.py           # Run evaluations
    └── test_dataset_loading.py        # Verify dataset integrity
```

---

## Quick Commands

```bash
# 1️⃣ Test dataset loading
cd aierplanggraph/ai_assistant
python test_dataset_loading.py

# 2️⃣ Create LangSmith dataset
python langsmith_evaluation.py --dataset-only

# 3️⃣ Quick evaluation (first 3 cases)
python langsmith_example.py --quick

# 4️⃣ Full evaluation with report
python langsmith_example.py --full --report
```

---

## File Characteristics

### api_test.json
- **Lines**: 252
- **Size**: 5.6 KB
- **Format**: Valid OpenAPI 3.0.1
- **Endpoints**: 9
- **Updates**: When API changes
- **Content**: NO test cases (cleaned)

### api_test_prompts.json
- **Lines**: ~150
- **Size**: 4.5 KB
- **Format**: JSON array of prompt groups
- **Endpoints**: 9 (one group per endpoint)
- **Prompts per endpoint**: 5
- **Total prompts**: 45
- **Languages**: French + English
- **Use case**: Prompt testing, fine-tuning

### api_test_evaluation.json
- **Lines**: ~450
- **Size**: 13.7 KB
- **Format**: JSON array of cases
- **Cases**: 45 (5 per endpoint)
- **Fields**: prompt, expected(endpoint, params, intent, domain)
- **Use case**: LangSmith ground truth evaluation
- **Loaded by**: langsmith_evaluation.py

---

## Example Flows

### Flow 1: Test Endpoint Selection Accuracy
```
api_test_evaluation.json
    ↓ (load 45 cases)
langsmith_evaluation.py
    ↓ (create dataset)
LangSmith
    ↓ (evaluate with EndpointExactMatchEvaluator)
Result: 87% accuracy (example)
```

### Flow 2: Evaluate Parameter Extraction
```
api_test_evaluation.json
    ↓ (prompt + expected_params)
LangSmith
    ↓ (ParameterExtractionEvaluator)
Result: 84% parameter accuracy (fuzzy)
```

### Flow 3: Test Prompt Variations
```
api_test_prompts.json
    ↓ (5 prompts per endpoint)
Your LLM
    ↓ (same endpoint, different wordings)
Analysis: Which prompt works best?
```

---

## Maintenance Checklist

### Adding a New Endpoint
- [ ] Add to `api_test.json` paths
- [ ] Add 5 prompts to `api_test_prompts.json`
- [ ] Add 5 evaluation cases to `api_test_evaluation.json`
- [ ] Update `DATASET_ARCHITECTURE.md`
- [ ] Run `test_dataset_loading.py`

### Updating API Definition
- [ ] Modify `api_test.json`
- [ ] Update related prompts in `api_test_prompts.json`
- [ ] Update evaluation cases in `api_test_evaluation.json`
- [ ] Verify with `test_dataset_loading.py`
- [ ] Rerun LangSmith evaluation

### Quality Assurance
- [ ] `python test_dataset_loading.py` - Verify 45 cases load
- [ ] Check each endpoint has 5 cases
- [ ] Validate parameter names match api_test.json
- [ ] Test with `langsmith_evaluation.py --dataset-only`

---

## Status Summary

| Item | Status | Evidence |
|------|--------|----------|
| api_test.json cleaned | ✅ | Reduced to 252 lines (no test_cases) |
| api_test_prompts.json | ✅ | 45 prompts (5×9 endpoints) |
| api_test_evaluation.json | ✅ | 45 cases with expected outputs |
| langsmith_evaluation.py updated | ✅ | Loads from evaluation.json |
| Dataset loading test | ✅ | All 45 cases verified |
| Documentation complete | ✅ | DATASET_ARCHITECTURE.md + this guide |

---

## Troubleshooting

### Issue: "api_test_evaluation.json not found"
**Solution**: Verify file is in `aierplanggraph/` directory
```bash
ls -la aierplanggraph/api_test_evaluation.json
```

### Issue: "Only X test cases loaded"
**Solution**: Check evaluation.json has proper JSON structure
```bash
python -m json.tool aierplanggraph/api_test_evaluation.json
```

### Issue: "Endpoint mismatch in evaluation"
**Solution**: Verify endpoint names match between files
- Check spelling in api_test.json paths
- Compare with api_test_evaluation.json expected.endpoint values
- Run validation script in DATASET_ARCHITECTURE.md

---

## Key Insights

1. **api_test.json** = Single Source of Truth
   - Never modify endpoints here manually
   - Reference it when updating prompts/evaluations

2. **api_test_prompts.json** = Reusable Asset
   - Can be used with any LLM system
   - Independent of LangSmith
   - Good for fine-tuning datasets

3. **api_test_evaluation.json** = Ground Truth Labels
   - Used exclusively for LangSmith
   - Each prompt must map to one endpoint
   - Parameters must be realistic/achievable

4. **Relationship**: evaluation ⊂ prompts ⊂ spec
   - Every evaluation case has a prompt
   - Every prompt references an endpoint
   - Every endpoint must be in api_test.json

---

## Next Steps

✅ **Current Status**: All three datasets created and verified

**To run LangSmith evaluation**:
```bash
cd ai_assistant
export LANGSMITH_API_KEY="your_key"
python langsmith_evaluation.py --dataset-only
python langsmith_example.py --quick
```

**To expand**:
- Add more prompts to api_test_prompts.json (no limit)
- Add more evaluation cases to api_test_evaluation.json
- Add new endpoints as needed

**To maintain**:
- Keep api_test.json as source of truth
- Sync prompts/evaluation whenever api_test.json changes
- Use test_dataset_loading.py for validation
