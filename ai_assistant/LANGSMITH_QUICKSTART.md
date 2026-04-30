# LangSmith Evaluation - Quick Reference

Complete LangSmith evaluation system for your LangGraph workflow focusing on parameter extraction and endpoint selection.

## 📦 Generated Files

### Core Scripts
1. **`langsmith_evaluation.py`** (Main)
   - Defines 10 test cases for different domains
   - Implements 4 custom evaluators
   - Creates LangSmith datasets
   - Supports async evaluation with `ainvoke`

2. **`langsmith_example.py`** (Runner)
   - Easy-to-use CLI for quick/full evaluation
   - Generates HTML reports
   - Batch processing with retry logic

3. **`langsmith_config.py`** (Configuration)
   - Environment variable management
   - Result analysis and aggregation
   - Caching and report generation
   - Batch evaluation runner

4. **`langsmith_integration.py`** (Integration)
   - Direct node tracing decorators
   - Parameter extraction tracing
   - Endpoint selection tracing
   - Integrated trace context

### Documentation
- **`LANGSMITH_GUIDE.md`** - Comprehensive guide (60+ pages)
- **`langsmith_requirements.txt`** - Python dependencies
- **`QUICKSTART.md`** - This file

## 🚀 Quick Start (5 Minutes)

### 1. Install Dependencies
```bash
pip install -r langsmith_requirements.txt
```

### 2. Set API Key
```powershell
$env:LANGSMITH_API_KEY = "your_api_key_here"
```

### 3. Create Dataset
```bash
python langsmith_evaluation.py --dataset-only
```

### 4. Run Quick Test
```bash
python langsmith_example.py --quick
```

### 5. Full Evaluation
```bash
python langsmith_example.py --full --report
```

## 📊 What Gets Tested

### Test Cases (10 total)
- Sales/Commercial queries (3 cases)
- Stock/Inventory queries (2 cases)
- Customer/CRM queries (2 cases)
- Finance/Invoice queries (1 case)
- Analytics/Aggregation queries (2 cases)

### Evaluated Components
- **Parameter Extraction**: Dates, IDs, filters
- **Endpoint Selection**: Correct API endpoint
- **Intent Classification**: GET, AGGREGATE, FILTER
- **Domain Classification**: commercial, stock, finance, etc.

### Metrics
| Metric | Score Range | What It Measures |
|--------|-------------|------------------|
| endpoint_exact_match | 0.0-1.0 | Correct endpoint selected |
| parameter_extraction_match | 0.0-1.0 | Parameters match expected |
| intent_classification | 0.0-1.0 | Correct intent detected |
| domain_classification | 0.0-1.0 | Correct domain classified |

## 🎯 Integration Steps

### Option 1: Direct Node Tracing (Easiest)

In your nodes, add the decorator:

```python
from langsmith_integration import trace_node

@trace_node("select_endpoint_and_params")
async def select_endpoint_and_params(state):
    # Your existing code
    return state
```

### Option 2: Manual Tracing

```python
from langsmith_integration import LangSmithTraceContext

async def my_workflow(question):
    with LangSmithTraceContext("my_workflow") as trace:
        trace.log_input(question)
        
        # ... your processing ...
        
        trace.log_endpoint_selection(endpoint, candidates)
        trace.log_parameters(params)
```

### Option 3: Full Integration (Most Comprehensive)

Modify `main.py` to use the evaluation graph:

```python
from langsmith_evaluation import build_evaluation_graph

# In build_graph():
app = build_evaluation_graph()  # Use evaluation version
result = await app.ainvoke({"question": question})
```

## 📈 Expected Results

Good performance targets:
- **endpoint_exact_match**: > 0.8 (80%+ correct)
- **parameter_extraction_match**: > 0.7 (70%+ correct)
- **intent_classification**: > 0.9 (90%+ correct)
- **domain_classification**: > 0.8 (80%+ correct)

## 🔧 Command Reference

```bash
# Create dataset only
python langsmith_evaluation.py --dataset-only

# Quick eval (first 3 cases)
python langsmith_example.py --quick

# Full eval (all cases)
python langsmith_example.py --full

# Generate HTML report
python langsmith_example.py --full --report

# Clear cache before eval
python langsmith_example.py --clear-cache --full

# With custom batch size
LANGSMITH_BATCH_SIZE=5 python langsmith_example.py --full

# With verbose logging
LANGSMITH_VERBOSE=true python langsmith_example.py --quick
```

## 🐛 Debugging

### Check Configuration
```python
from langsmith_config import LangSmithConfig
config = LangSmithConfig.from_env()
print(config.to_dict())
```

### View Failed Cases
```python
from langsmith_config import EvaluationResultAnalyzer
analyzer = EvaluationResultAnalyzer()
failures = analyzer.identify_failures(results)
for f in failures:
    print(f)
```

### Enable Logging
```bash
LANGSMITH_VERBOSE=true python langsmith_example.py --quick
```

## 🏗️ Architecture

```
LangSmith Evaluation System
├── langsmith_evaluation.py
│   ├── TEST_CASES (10 examples)
│   ├── Custom Evaluators (4 types)
│   ├── create_or_update_dataset()
│   ├── build_evaluation_graph()
│   └── run_test_case_async()
│
├── langsmith_example.py
│   ├── EvaluationRunner
│   ├── run_quick_eval()
│   ├── run_full_eval()
│   └── generate_report()
│
├── langsmith_config.py
│   ├── LangSmithConfig
│   ├── EvaluationResultAnalyzer
│   ├── BatchEvaluationRunner
│   └── EvaluationReportGenerator
│
└── langsmith_integration.py
    ├── setup_langsmith()
    ├── trace_node() decorator
    ├── ParameterExtractionTracer
    ├── EndpointSelectionTracer
    └── LangSmithTraceContext
```

## 📋 Adding Custom Test Cases

Edit `TEST_CASES` in `langsmith_evaluation.py`:

```python
TEST_CASES = [
    {
        "input": {
            "question": "Your test question",
        },
        "expected_output": {
            "endpoint_name": "GetAllVentes",
            "extracted_params": {
                "startDate": "2024-01-01",
                "endDate": "2024-12-31",
            },
            "intent": "GET",
            "domain": "commercial",
        }
    },
    # Add more...
]
```

Then re-create dataset:
```bash
python langsmith_evaluation.py --dataset-only
```

## 🔐 Security Notes

- Store `LANGSMITH_API_KEY` in `.env` file (don't commit)
- Use environment variables for configuration
- Cache is stored locally in `./langsmith_logs/`
- No sensitive data is sent to LangSmith unnecessarily

## 🚀 Next Steps

1. **Run quick eval**: `python langsmith_example.py --quick`
2. **Review results**: Check metrics and failed cases
3. **Add to nodes**: Integrate tracing with `@trace_node` decorator
4. **Add to CI/CD**: Setup automated evaluation on commits
5. **Monitor over time**: Track metrics as you improve the router

## 📚 Full Documentation

See `LANGSMITH_GUIDE.md` for:
- Detailed setup instructions
- Custom evaluator examples
- CI/CD integration
- Advanced usage patterns
- Troubleshooting guide

## 🤝 Support

For issues or questions:
1. Check `LANGSMITH_GUIDE.md` troubleshooting section
2. Enable verbose logging: `LANGSMITH_VERBOSE=true`
3. Review LangSmith docs: https://smith.langchain.com/docs
4. Check LangGraph docs: https://langchain-ai.github.io/langgraph/

---

**Version**: 1.0  
**Last Updated**: April 2026  
**Status**: Ready for production use
