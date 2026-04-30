# LangSmith Evaluation & Testing Guide

This guide provides a complete setup and usage instructions for evaluating your LangGraph endpoint selection and parameter extraction nodes using LangSmith.

## 📋 Overview

The evaluation system includes:

- **`langsmith_evaluation.py`**: Core evaluation script with dataset creation and custom evaluators
- **`langsmith_config.py`**: Configuration management and result analysis utilities
- **`langsmith_example.py`**: Practical runner with examples for quick testing

### What Gets Evaluated

1. **Parameter Extraction Node**: Validates that LLM correctly extracts parameters (dates, IDs, etc.)
2. **Endpoint Selection Node**: Ensures the correct API endpoint is selected for the question

### Custom Evaluators

- **EndpointExactMatchEvaluator**: Exact match on endpoint ID (strict)
- **ParameterExtractionEvaluator**: Fuzzy matching on parameter keys/values
- **IntentClassificationEvaluator**: Validates intent (GET, AGGREGATE, FILTER)
- **DomainClassificationEvaluator**: Validates domain classification

---

## 🚀 Quick Start

### 1. Set Up LangSmith API Key

```powershell
# PowerShell
$env:LANGSMITH_API_KEY = "your_api_key_here"

# Or set permanently
[System.Environment]::SetEnvironmentVariable("LANGSMITH_API_KEY", "your_key", "User")
```

### 2. Create Dataset

```bash
python langsmith_evaluation.py --dataset-only
```

This creates a LangSmith dataset with 10 test cases covering:
- Sales queries (commercial domain)
- Stock queries (inventory domain)
- Customer queries (CRM domain)
- Finance/Invoice queries
- Aggregation queries

### 3. Run Quick Evaluation

```bash
python langsmith_example.py --quick
```

Runs evaluation on first 3 test cases to verify setup.

### 4. Run Full Evaluation

```bash
python langsmith_example.py --full
```

Evaluates all test cases and displays metrics.

### 5. Generate Report

```bash
python langsmith_example.py --full --report
```

Creates an HTML report in `./langsmith_logs/evaluation_report.html`

---

## 📊 Understanding Results

### Metric Scores (0.0 - 1.0)

- **endpoint_exact_match**: Binary score
  - 1.0 = Correct endpoint selected
  - 0.0 = Wrong endpoint

- **parameter_extraction_match**: Fuzzy score based on:
  - Key matching (case-insensitive)
  - Value comparison with type coercion
  - Penalties for extra/missing keys
  - Score: 0.0 (all wrong) to 1.0 (all correct)

- **intent_classification**: Binary score
  - 1.0 = Correct intent (GET/AGGREGATE/FILTER)
  - 0.0 = Wrong intent

- **domain_classification**: Binary score
  - 1.0 = Correct domain (commercial/stock/finance/etc.)
  - 0.0 = Wrong domain

### Example Output

```
⏳ Running inference and evaluation...
  ✓ 1/10: Evaluated successfully
  ✓ 2/10: Evaluated successfully
  ✓ 3/10: Evaluated successfully
  ...

📊 Evaluation Complete!
======================================================================

✅ Metrics:

  endpoint_exact_match:
    Mean:  0.850
    Min:   0.000
    Max:   1.000

  parameter_extraction_match:
    Mean:  0.760
    Min:   0.250
    Max:   1.000

  intent_classification:
    Mean:  0.900
    Min:   1.000
    Max:   1.000

⚠️  Failed/Low-scoring cases: 2
  - sales_march_2024: Low score
  - unknown_domain_query: Low score
```

---

## 🔧 Configuration

### Environment Variables

```bash
# LangSmith
LANGSMITH_API_KEY=your_api_key              # Required
LANGSMITH_API_URL=https://api.smith.langchain.com
LANGSMITH_PROJECT=endpoint_selection_evaluation
LANGSMITH_DATASET=endpoint_selection_test_cases

# Evaluation Parameters
LANGSMITH_MODE=async                        # sync, async, batch
LANGSMITH_BATCH_SIZE=10
LANGSMITH_MAX_WORKERS=4
LANGSMITH_TIMEOUT=300
LANGSMITH_VERBOSE=true
```

### Python Configuration

Edit in `langsmith_config.py`:

```python
config = LangSmithConfig(
    project_name="my_project",
    dataset_name="my_dataset",
    mode=EvaluationMode.ASYNC,
    batch_size=10,
    max_workers=4,
    timeout_seconds=300,
    verbose=True,
)
```

---

## 📝 Adding Test Cases

### Modify Test Dataset

Edit `TEST_CASES` list in `langsmith_evaluation.py`:

```python
TEST_CASES = [
    {
        "input": {
            "question": "Your test question here",
        },
        "expected_output": {
            "endpoint_name": "ExpectedEndpointId",
            "endpoint_keywords": ["keyword1", "keyword2"],
            "extracted_params": {
                "param1": "value1",
                "param2": 123,
            },
            "intent": "GET",           # GET, AGGREGATE, FILTER
            "domain": "commercial",    # commercial, stock, finance, rh, achat
        }
    },
    # Add more test cases...
]
```

### Supported Domains

- `commercial`: Sales, orders, customers
- `stock`: Inventory, articles, warehouse
- `finance`: Invoices, payments, accounting
- `rh`: Human resources, employees
- `achat`: Procurement, suppliers
- `general`: Default/unknown

### Supported Intents

- `GET`: Retrieve records by ID or filter
- `AGGREGATE`: Group/summarize/count
- `FILTER`: Apply business filters

---

## 🧪 Custom Evaluators

### Creating a Custom Evaluator

```python
from langsmith.evaluation import LangSmithStringEvaluator

class MyCustomEvaluator(LangSmithStringEvaluator):
    """Custom evaluator for specific metric."""
    
    def _evaluate_strings(self, prediction: str, reference: str, **kwargs):
        # Your evaluation logic
        is_match = prediction.lower() == reference.lower()
        
        return {
            "key": "my_custom_metric",
            "score": 1.0 if is_match else 0.0,
            "details": {
                "predicted": prediction,
                "expected": reference,
            }
        }
```

### Using in Evaluation

```python
evaluators = [
    EndpointExactMatchEvaluator(),
    MyCustomEvaluator(),
]

results = await batch_runner.run_batch(
    examples,
    inference_fn,
    evaluators,
)
```

---

## 🔍 Debugging Failed Cases

### View Detailed Results

```python
from langsmith_config import EvaluationResultAnalyzer

analyzer = EvaluationResultAnalyzer()
failures = analyzer.identify_failures(results)

for failure in failures:
    print(f"Failed: {failure['example_id']}")
    print(f"  Input: {failure['input']}")
    print(f"  Expected: {failure['expected']}")
    print(f"  Predicted: {failure['prediction']}")
    print(f"  Scores: {failure['scores']}")
```

### Enable Verbose Logging

```bash
LANGSMITH_VERBOSE=true python langsmith_example.py --full
```

### Run with Debugger

```bash
# Use VS Code debugger or Python debugger
python -m pdb langsmith_example.py --quick
```

---

## 📊 Advanced Usage

### Batch Processing

```bash
LANGSMITH_MODE=batch LANGSMITH_BATCH_SIZE=5 python langsmith_example.py --full
```

### Increase Parallelism

```bash
LANGSMITH_MAX_WORKERS=8 python langsmith_example.py --full
```

### Generate Comparative Report

```python
from langsmith import Client

client = Client()

# Run two versions
results_v1 = await runner.run_full_eval()
results_v2 = await runner.run_full_eval()

# Compare
from langsmith.evaluation import evaluate_comparative
comparison = evaluate_comparative(
    [client.read_run(r["run_id"]) for r in results_v1],
    [client.read_run(r["run_id"]) for r in results_v2],
)
```

### Export Results to CSV

```python
import csv

def export_results_to_csv(results, output_path):
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'example_id', 'question', 'predicted_endpoint', 
            'expected_endpoint', 'endpoint_match_score', 'param_match_score'
        ])
        writer.writeheader()
        for result in results:
            writer.writerow({
                'example_id': result.get('example_id'),
                'question': result.get('input', {}).get('question'),
                'predicted_endpoint': result.get('prediction', {}).get('endpoint_name'),
                'expected_endpoint': result.get('expected', {}).get('endpoint_name'),
                'endpoint_match_score': result.get('scores', {}).get('endpoint_exact_match', 0),
                'param_match_score': result.get('scores', {}).get('parameter_extraction_match', 0),
            })

export_results_to_csv(results, 'results.csv')
```

---

## 🚨 Troubleshooting

### Error: LANGSMITH_API_KEY not set

```powershell
$env:LANGSMITH_API_KEY = 'your_key_here'
python langsmith_example.py --quick
```

### Error: Dataset not found

Create the dataset first:
```bash
python langsmith_evaluation.py --dataset-only
```

### Slow Inference

- Reduce batch size: `LANGSMITH_BATCH_SIZE=5`
- Increase timeout: `LANGSMITH_TIMEOUT=600`
- Run in async mode: `LANGSMITH_MODE=async`

### Low Scores

1. **Review test cases**: Are expected outputs correct?
2. **Check endpoint metadata**: Ensure endpoints are loaded correctly
3. **Validate parameters**: Do extracted params make sense for the question?
4. **Inspect LLM output**: Enable verbose logging to see what DeepSeek returns

### Memory Issues

- Run with fewer workers: `LANGSMITH_MAX_WORKERS=2`
- Reduce batch size: `LANGSMITH_BATCH_SIZE=5`
- Clear cache: `python langsmith_example.py --clear-cache`

---

## 📚 Integration with CI/CD

### GitHub Actions Example

```yaml
name: LangSmith Evaluation

on: [push, pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run LangSmith Evaluation
        env:
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
        run: python langsmith_example.py --full --report
      
      - name: Upload Report
        uses: actions/upload-artifact@v2
        with:
          name: evaluation-report
          path: langsmith_logs/evaluation_report.html
```

---

## 📖 Additional Resources

- [LangSmith Documentation](https://smith.langchain.com/docs)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Evaluation Guide](https://python.langchain.com/docs/guides/evaluation/)

---

## 💡 Best Practices

1. **Keep test cases fresh**: Update as your endpoints evolve
2. **Monitor metrics**: Track endpoint_exact_match > 0.8 and param_extraction > 0.7
3. **Fail fast**: Fix low-scoring test cases immediately
4. **Version your datasets**: Keep snapshots for regression testing
5. **Use CI/CD**: Automate evaluation on every commit
6. **Review failures**: Manually inspect failed cases to understand patterns
7. **Iterate**: Use evaluation results to improve your router prompt/logic

---

**Generated**: LangSmith Integration Guide for LangGraph Endpoint Selection
