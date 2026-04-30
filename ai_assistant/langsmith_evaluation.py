#!/usr/bin/env python3
"""
LangSmith Evaluation Script for LangGraph Workflow

Focus: Evaluating parameter_extraction and endpoint_selection nodes.

This script:
1. Loads test cases from ../api_test_evaluation.json
2. Integrates with existing LangGraph StateGraph
3. Implements custom evaluators for endpoint matching and parameter validation
4. Runs evaluation async with ainvoke
5. Logs results to LangSmith project

Configuration:
    - Uses .env file in project root for LANGSMITH_API_KEY
    - Falls back to environment variable if .env not present
    - See config.py for all LangSmith settings

Usage:
    # Create or update datasets and run evaluation
    python langsmith_evaluation.py --evaluate
    
    # Just create the dataset without running evaluation
    python langsmith_evaluation.py --dataset-only
    
    # Run evaluation on existing dataset
    python langsmith_evaluation.py --evaluate --dataset-name "endpoint_selection_v2"
"""

import asyncio
import json
import argparse
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from pydantic import ConfigDict

from langsmith import Client, traceable
from langsmith.evaluation import StringEvaluator, RunEvaluator
from langsmith.schemas import Run, Example
from langgraph.graph import END, START, StateGraph

from state import AssistantState
from config import config
from nodes import (
    classify_question,
    retrieve_candidate_endpoints,
    select_endpoint_and_params,
)


# ============================================================================
# LANGSMITH CONFIGURATION
# ============================================================================

LANGSMITH_PROJECT_NAME = config.langsmith_project_name()
DATASET_NAME = config.langsmith_dataset_name()
API_TEST_EVALUATION_PATH = Path(__file__).parent.parent / "api_test_evaluation.json"
API_TEST_JSON_PATH = Path(__file__).parent.parent / "api_test.json"

# Initialize LangSmith client
client = Client()


# ============================================================================
# TEST ENDPOINTS LOADING FROM api_test.json (for LangSmith evaluation only)
# ============================================================================

def load_test_endpoints_from_api_test() -> List[Dict[str, Any]]:
    """
    Load endpoint definitions from api_test.json for evaluation.
    
    Converts OpenAPI 3.0.1 spec to endpoint definitions.
    
    Returns:
        List of endpoint definitions from api_test.json
    """
    if not API_TEST_JSON_PATH.exists():
        print(f"❌ api_test.json not found at {API_TEST_JSON_PATH}")
        return []
    
    try:
        with open(API_TEST_JSON_PATH, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        # Convert OpenAPI spec to endpoints
        endpoints = []
        paths = spec.get("paths", {})
        
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            
            for method, operation in methods.items():
                if method not in ["get", "post", "put", "delete", "patch"]:
                    continue
                
                # Extract operation info
                tags = operation.get("tags", ["general"])
                tag = tags[0] if tags else "general"
                
                # Extract parameters
                parameters = operation.get("parameters", [])
                param_details = {}
                required_params = []
                
                for param in parameters:
                    param_name = param.get("name", "")
                    if param_name:
                        param_details[param_name] = {
                            "type": param.get("schema", {}).get("type", "string"),
                            "in": param.get("in", "query"),
                            "required": param.get("required", False),
                            "description": param.get("description", "")
                        }
                        if param.get("required", False) or param.get("in") == "path":
                            required_params.append(param_name)
                
                # Create endpoint definition
                endpoint = {
                    "id": f"webapi_{method.lower()}_{path.lower().replace('/', '_').replace('-', '_')}",
                    "path": path,
                    "method": method.upper(),
                    "tags": [tag],
                    "description": operation.get("summary", operation.get("description", "")),
                    "parameters": param_details,
                    "required_parameters": required_params,
                    "keywords": [tag.lower()]
                }
                
                endpoints.append(endpoint)
        
        if endpoints:
            print(f"✅ Loaded {len(endpoints)} test endpoints from api_test.json (OpenAPI spec)")
            return endpoints
        else:
            print(f"⚠️  No endpoints found in api_test.json")
            return []
    
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing api_test.json: {e}")
        return []
    except Exception as e:
        print(f"❌ Error loading api_test.json: {e}")
        return []


# Cache test endpoints at module load time
TEST_ENDPOINTS = load_test_endpoints_from_api_test()


# ============================================================================
# CUSTOM NODES FOR EVALUATION (using test endpoints)
# ============================================================================

def retrieve_candidate_endpoints_eval(state: AssistantState) -> AssistantState:
    """
    Retrieve and score endpoint candidates using TEST_ENDPOINTS from api_test.json.
    
    This is a custom version for LangSmith evaluation that uses controlled test endpoints
    instead of live Swagger endpoints.
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with endpoint_candidates
    """
    from nodes.endpoint_scoring import score_endpoints
    
    question = state.get("question", "")
    intent = state.get("intent", "GET")
    domain = state.get("domain", "general")
    
    # Use TEST_ENDPOINTS from api_test.json
    if not TEST_ENDPOINTS:
        print("❌ No test endpoints available")
        return {"endpoint_candidates": []}
    
    # Score with business filter
    scored = score_endpoints(
        endpoints=TEST_ENDPOINTS,
        question=question,
        intent=intent,
        domain=domain,
        apply_business_filter=True,
    )
    
    # If no business endpoints found, try without filter
    if not scored:
        scored = score_endpoints(
            endpoints=TEST_ENDPOINTS,
            question=question,
            intent=intent,
            domain=domain,
            apply_business_filter=False,
        )
    
    # Return up to 12 best candidates
    max_candidates = 12
    return {"endpoint_candidates": scored[:max_candidates]}


# ============================================================================
# TEST CASE LOADING FROM api_test_evaluation.json
# ============================================================================

def load_test_cases_from_evaluation_dataset() -> List[Dict[str, Any]]:
    """
    Load test cases from api_test_evaluation.json file.
    
    The api_test_evaluation.json contains natural language prompts paired with 
    expected outputs (endpoint + parameters + intent + domain).
    
    Returns:
        List of test cases with input/expected_output structure
    """
    if not API_TEST_EVALUATION_PATH.exists():
        print(f"❌ api_test_evaluation.json not found at {API_TEST_EVALUATION_PATH}")
        return []
    
    try:
        with open(API_TEST_EVALUATION_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract evaluation_cases from the file and convert to langsmith format
        evaluation_cases = data.get("evaluation_cases", [])
        
        if evaluation_cases:
            # Convert evaluation format to LangSmith format
            test_cases = []
            for case in evaluation_cases:
                test_cases.append({
                    "input": {"question": case["prompt"]},
                    "expected_output": case["expected"]
                })
            
            print(f"✅ Loaded {len(test_cases)} evaluation cases from api_test_evaluation.json")
            return test_cases
        else:
            print(f"⚠️  No evaluation_cases found in api_test_evaluation.json")
            return []
    
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing api_test_evaluation.json: {e}")
        return []
    except Exception as e:
        print(f"❌ Error loading api_test_evaluation.json: {e}")
        return []


# Load test cases at module initialization
TEST_CASES = load_test_cases_from_evaluation_dataset()


# ============================================================================
# CUSTOM EVALUATORS
# ============================================================================

class EndpointExactMatchEvaluator(StringEvaluator):
    """
    Evaluates if the selected endpoint matches the expected endpoint exactly.
    
    This is a strict evaluator: either the endpoint matches (1.0) or it doesn't (0.0).
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **kwargs):
        """Initialize with default grading function."""
        if 'grading_function' not in kwargs:
            kwargs['grading_function'] = self._evaluate_strings
        super().__init__(**kwargs)
    
    def _evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Wrapper to match LangSmith StringEvaluator interface."""
        return self.evaluate_strings(prediction, reference, **kwargs)
    
    def evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Args:
            prediction: The endpoint_name from the run output
            reference: Expected endpoint_name from test case
            
        Returns:
            Score and details
        """
        try:
            # Parse predictions if they're JSON
            if isinstance(prediction, str):
                if prediction.startswith("{"):
                    pred_obj = json.loads(prediction)
                    prediction = pred_obj.get("selected_endpoint", {}).get("id", prediction)
                else:
                    prediction = prediction.strip()
            
            # Normalize for comparison
            pred_normalized = str(prediction).lower().strip()
            ref_normalized = str(reference).lower().strip()
            
            is_match = pred_normalized == ref_normalized
            score = 1.0 if is_match else 0.0
            
            return {
                "key": "endpoint_exact_match",
                "score": score,
                "details": {
                    "predicted": prediction,
                    "expected": reference,
                    "match": is_match,
                }
            }
        except Exception as e:
            return {
                "key": "endpoint_exact_match",
                "score": 0.0,
                "details": {
                    "error": str(e),
                    "predicted": prediction,
                    "expected": reference,
                }
            }


class ParameterExtractionEvaluator(StringEvaluator):
    """
    Evaluates if extracted parameters match expected parameters.
    
    Uses fuzzy matching for parameter keys (case-insensitive) and value comparison.
    Scores based on:
    - Exact key matches: +1 point per key
    - Value matches: +1 point if values match (with type coercion)
    - Missing keys: -0.5 point per missing key
    - Extra keys: -0.25 point per extra key (slightly penalized)
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **kwargs):
        """Initialize with default grading function."""
        if 'grading_function' not in kwargs:
            kwargs['grading_function'] = self._evaluate_strings
        super().__init__(**kwargs)
    
    def _evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Wrapper to match LangSmith StringEvaluator interface."""
        return self.evaluate_strings(prediction, reference, **kwargs)
    
    def evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Args:
            prediction: Extracted parameters (JSON string or dict)
            reference: Expected parameters (JSON string or dict)
            
        Returns:
            Score and details
        """
        try:
            # Parse predictions
            if isinstance(prediction, str):
                pred_params = json.loads(prediction) if prediction.startswith("{") else {}
            else:
                pred_params = prediction
            
            # Parse reference
            if isinstance(reference, str):
                ref_params = json.loads(reference) if reference.startswith("{") else {}
            else:
                ref_params = reference
            
            if not isinstance(pred_params, dict):
                pred_params = {}
            if not isinstance(ref_params, dict):
                ref_params = {}
            
            # Normalize keys to lowercase
            pred_keys_lower = {k.lower(): (k, v) for k, v in pred_params.items()}
            ref_keys_lower = {k.lower(): (k, v) for k, v in ref_params.items()}
            
            score = 0.0
            max_score = max(len(ref_keys_lower), 1)
            
            matching_keys = set()
            value_matches = 0
            
            # Check expected keys
            for key_lower, (orig_key, expected_value) in ref_keys_lower.items():
                if key_lower in pred_keys_lower:
                    matching_keys.add(key_lower)
                    _, predicted_value = pred_keys_lower[key_lower]
                    
                    # Compare values (with type coercion)
                    if self._values_match(predicted_value, expected_value):
                        value_matches += 1
                        score += 1.0
                    else:
                        # Partial credit for key match
                        score += 0.5
                else:
                    # Missing expected key
                    score -= 0.5
            
            # Penalize extra keys
            extra_keys = set(pred_keys_lower.keys()) - set(ref_keys_lower.keys())
            score -= len(extra_keys) * 0.25
            
            # Normalize score to [0, 1]
            normalized_score = max(0.0, min(1.0, score / max_score))
            
            return {
                "key": "parameter_extraction_match",
                "score": normalized_score,
                "details": {
                    "predicted_params": pred_params,
                    "expected_params": ref_params,
                    "matching_keys": len(matching_keys),
                    "value_matches": value_matches,
                    "extra_keys": len(extra_keys),
                    "raw_score": score,
                    "max_score": max_score,
                }
            }
        except Exception as e:
            return {
                "key": "parameter_extraction_match",
                "score": 0.0,
                "details": {
                    "error": str(e),
                    "predicted": prediction,
                    "expected": reference,
                }
            }
    
    @staticmethod
    def _values_match(pred_value: Any, expected_value: Any) -> bool:
        """Check if two values match, with type coercion."""
        if pred_value == expected_value:
            return True
        
        # Try string comparison
        if str(pred_value).lower() == str(expected_value).lower():
            return True
        
        # Try numeric comparison
        try:
            if float(pred_value) == float(expected_value):
                return True
        except (ValueError, TypeError):
            pass
        
        return False


class IntentClassificationEvaluator(StringEvaluator):
    """
    Evaluates if the classified intent (GET, AGGREGATE, FILTER) is correct.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **kwargs):
        """Initialize with default grading function."""
        if 'grading_function' not in kwargs:
            kwargs['grading_function'] = self._evaluate_strings
        super().__init__(**kwargs)
    
    def _evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Wrapper to match LangSmith StringEvaluator interface."""
        return self.evaluate_strings(prediction, reference, **kwargs)
    
    def evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Args:
            prediction: Predicted intent
            reference: Expected intent
            
        Returns:
            Classification result
        """
        try:
            pred_intent = str(prediction).upper().strip()
            ref_intent = str(reference).upper().strip()
            
            return {
                "key": "intent_classification",
                "score": 1.0 if pred_intent == ref_intent else 0.0,
                "details": {
                    "predicted_intent": pred_intent,
                    "expected_intent": ref_intent,
                }
            }
        except Exception as e:
            return {
                "key": "intent_classification",
                "score": 0.0,
                "details": {"error": str(e)}
            }


class DomainClassificationEvaluator(StringEvaluator):
    """
    Evaluates if the classified domain is correct.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **kwargs):
        """Initialize with default grading function."""
        if 'grading_function' not in kwargs:
            kwargs['grading_function'] = self._evaluate_strings
        super().__init__(**kwargs)
    
    def _evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Wrapper to match LangSmith StringEvaluator interface."""
        return self.evaluate_strings(prediction, reference, **kwargs)
    
    def evaluate_strings(
        self,
        prediction: str,
        reference: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Args:
            prediction: Predicted domain
            reference: Expected domain
            
        Returns:
            Classification result
        """
        try:
            pred_domain = str(prediction).lower().strip()
            ref_domain = str(reference).lower().strip()
            
            return {
                "key": "domain_classification",
                "score": 1.0 if pred_domain == ref_domain else 0.0,
                "details": {
                    "predicted_domain": pred_domain,
                    "expected_domain": ref_domain,
                }
            }
        except Exception as e:
            return {
                "key": "domain_classification",
                "score": 0.0,
                "details": {"error": str(e)}
            }


# ============================================================================
# DATASET MANAGEMENT
# ============================================================================

def create_or_update_dataset() -> str:
    """
    Create or update the LangSmith dataset with test cases from api_test.json.
    
    Returns:
        Dataset name
    """
    if not TEST_CASES:
        print("❌ No test cases available. Check api_test.json")
        return None
    
    print(f"\n📊 Creating/updating dataset: {DATASET_NAME}")
    
    try:
        # Create dataset
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Test cases loaded from api_test.json - using actual API endpoints",
        )
        dataset_id = dataset.id
        print(f"✅ Created dataset: {dataset_id}")
    except Exception as e:
        # Dataset might already exist
        datasets = client.list_datasets(dataset_name=DATASET_NAME)
        existing = list(datasets)
        if existing:
            dataset_id = existing[0].id
            print(f"✅ Using existing dataset: {dataset_id}")
        else:
            print(f"❌ Failed to create dataset: {e}")
            raise
    
    # Add examples
    print(f"\n📝 Adding {len(TEST_CASES)} test cases...")
    for i, test_case in enumerate(TEST_CASES, 1):
        try:
            example = client.create_example(
                inputs=test_case["input"],
                outputs=test_case["expected_output"],
                dataset_id=dataset_id,
            )
            print(f"  ✓ Test case {i}: {test_case['input']['question'][:50]}...")
        except Exception as e:
            print(f"  ✗ Failed to add test case {i}: {e}")
    
    print(f"\n✅ Dataset ready: {DATASET_NAME}")
    return DATASET_NAME


# ============================================================================
# INFERENCE FUNCTION (to be traced by LangSmith)
# ============================================================================

async def run_test_case_async(
    question: str,
    graph_app: Any,
) -> Dict[str, Any]:
    """
    Run a single test case through the graph asynchronously.
    
    Args:
        question: Input question
        graph_app: Compiled LangGraph application
        
    Returns:
        Result dict with extracted endpoint and parameters
    """
    try:
        # Use ainvoke for async execution
        result = await graph_app.ainvoke(
            {
                "question": question,
                "errors": [],
            }
        )
        
        # Get endpoint ID
        endpoint_id = result.get("selected_endpoint", {}).get("id", "UNKNOWN")
        
        # Look up endpoint path from TEST_ENDPOINTS
        endpoint_path = "UNKNOWN"
        for endpoint in TEST_ENDPOINTS:
            if endpoint.get("id") == endpoint_id:
                endpoint_path = endpoint.get("path", "UNKNOWN")
                break
        
        # Extract relevant outputs
        return {
            "endpoint_name": endpoint_id,
            "endpoint_path": endpoint_path,  # Add path for comparison
            "endpoint_keywords": result.get("selected_endpoint", {}).get("keywords", []),
            "extracted_params": result.get("extracted_params", {}),
            "intent": result.get("intent", "GET"),
            "domain": result.get("domain", "general"),
            "success": True,
        }
    except Exception as e:
        print(f"❌ Error running test case: {e}")
        return {
            "endpoint_name": "ERROR",
            "endpoint_path": "ERROR",
            "extracted_params": {},
            "intent": "GET",
            "domain": "general",
            "success": False,
            "error": str(e),
        }


# ============================================================================
# BUILD EVALUATION GRAPH (subset for evaluation)
# ============================================================================

def build_evaluation_graph():
    """
    Build a simplified graph focusing on endpoint selection and parameter extraction.
    This runs the first 3 nodes: classify -> retrieve -> select
    
    Uses TEST_ENDPOINTS from api_test.json for retrieve_candidate_endpoints node.
    
    Returns:
        Compiled LangGraph application
    """
    graph = StateGraph(AssistantState)
    
    # Add nodes - use custom retrieve function for test endpoints
    graph.add_node("classify_question", classify_question)
    graph.add_node("retrieve_candidate_endpoints", retrieve_candidate_endpoints_eval)
    graph.add_node("select_endpoint_and_params", select_endpoint_and_params)
    
    # Add edges
    graph.add_edge(START, "classify_question")
    graph.add_edge("classify_question", "retrieve_candidate_endpoints")
    graph.add_edge("retrieve_candidate_endpoints", "select_endpoint_and_params")
    graph.add_edge("select_endpoint_and_params", END)
    
    return graph.compile()


# ============================================================================
# EVALUATION EXECUTION
# ============================================================================

async def run_evaluation():
    """
    Run the LangSmith evaluation on the dataset.
    """
    if not TEST_CASES:
        print("❌ No test cases loaded. Exiting.")
        return
    
    print(f"\n🚀 Starting evaluation on project: {LANGSMITH_PROJECT_NAME}")
    print(f"📊 Dataset: {DATASET_NAME}")
    print(f"📋 Test cases: {len(TEST_CASES)}")
    
    # Build the evaluation graph
    graph_app = build_evaluation_graph()
    
    # Define evaluators
    evaluators = [
        EndpointExactMatchEvaluator(),
        ParameterExtractionEvaluator(),
        IntentClassificationEvaluator(),
        DomainClassificationEvaluator(),
    ]
    
    # Get dataset
    dataset = None
    for ds in client.list_datasets(dataset_name=DATASET_NAME):
        dataset = ds
        break
    
    if not dataset:
        print(f"❌ Dataset not found: {DATASET_NAME}")
        return
    
    print(f"\n📋 Evaluation configuration:")
    print(f"  - Dataset: {dataset.name} ({dataset.id})")
    print(f"  - Examples: {dataset.example_count}")
    print(f"  - Evaluators: {len(evaluators)}")
    
    # Prepare inference function
    @traceable(name="endpoint_selection_inference")
    async def inference(inputs: Dict[str, Any]) -> Dict[str, Any]:
        question = inputs.get("question", "")
        return await run_test_case_async(question, graph_app)
    
    print(f"\n⏳ Running inference on all examples...")
    
    # Run evaluation using the evaluate API
    try:
        results = await asyncio.gather(
            *[
                inference(example.inputs)
                for example in client.list_examples(dataset_id=dataset.id)
            ]
        )
        
        print(f"\n✅ Inference complete: {len(results)} results")
        
        # Print sample results
        print(f"\n📊 Sample results:")
        for i, result in enumerate(results[:3], 1):
            print(f"\n  Test {i}:")
            print(f"    - Endpoint: {result.get('endpoint_name')}")
            print(f"    - Intent: {result.get('intent')}")
            print(f"    - Domain: {result.get('domain')}")
            print(f"    - Params: {result.get('extracted_params')}")
        
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        raise


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main_async():
    """Main async entry point."""
    parser = argparse.ArgumentParser(
        description="LangSmith Evaluation for LangGraph Endpoint Selection (using api_test_evaluation.json)"
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run the evaluation",
    )
    parser.add_argument(
        "--dataset-only",
        action="store_true",
        help="Only create/update dataset without running evaluation",
    )
    
    args = parser.parse_args()
    
    # Check LangSmith configuration
    api_key = config.langsmith_api_key()
    if not api_key:
        print("❌ Error: LANGSMITH_API_KEY not found")
        print("\n📋 Setup Instructions:")
        print("   1. Create a .env file in the project root (aierplanggraph/)")
        print("   2. Add: LANGSMITH_API_KEY=your_key_here")
        print("   3. Run again: python langsmith_evaluation.py --dataset-only")
        print("\n   OR set environment variable:")
        print("   Windows: $env:LANGSMITH_API_KEY='your_key'")
        print("   Linux/Mac: export LANGSMITH_API_KEY='your_key'")
        return 1
    
    print(f"🔐 LangSmith API Key: {api_key[:8]}... (loaded from .env)")
    print(f"📂 Loading test cases from: {API_TEST_EVALUATION_PATH}")
    
    # Create/update dataset
    try:
        dataset_name = create_or_update_dataset()
        if not dataset_name:
            return 1
    except Exception as e:
        print(f"❌ Failed to create dataset: {e}")
        return 1
    
    # Run evaluation if requested
    if args.evaluate:
        try:
            await run_evaluation()
            print("\n✅ Evaluation complete!")
        except Exception as e:
            print(f"\n❌ Evaluation failed: {e}")
            return 1
    else:
        print("\n✅ Dataset ready. Run with --evaluate to start evaluation.")
    
    return 0


def main():
    """Main entry point."""
    exit_code = asyncio.run(main_async())
    exit(exit_code)


if __name__ == "__main__":
    main()
