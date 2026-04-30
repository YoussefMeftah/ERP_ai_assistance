#!/usr/bin/env python3
"""
LangSmith Integration Module

Provides utilities for integrating LangSmith tracing directly into your nodes.
This enables automatic tracing of all inference and decisions.

Usage:
    from langsmith_integration import setup_langsmith, trace_node
    
    # Setup once at startup
    setup_langsmith("my_project_name")
    
    # Decorate your node functions
    @trace_node("my_node")
    async def my_node(state: AssistantState) -> AssistantState:
        # Your logic here
        return state
"""

import os
import json
from functools import wraps
from typing import Any, Callable, Dict, Optional
from langsmith import Client, traceable
from langsmith.evaluation import LangSmithStringEvaluator
from langsmith.schemas import Run
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# SETUP AND CONFIGURATION
# ============================================================================

_langsmith_client: Optional[Client] = None
_langsmith_project: Optional[str] = None


def setup_langsmith(project_name: str = "endpoint_selection") -> Client:
    """
    Initialize LangSmith client and set project name.
    
    Args:
        project_name: LangSmith project name for this run
        
    Returns:
        Configured Client instance
    """
    global _langsmith_client, _langsmith_project
    
    api_key = os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        logger.warning("LANGSMITH_API_KEY not set. Tracing disabled.")
        return None
    
    _langsmith_client = Client(api_key=api_key)
    _langsmith_project = project_name
    
    logger.info(f"✅ LangSmith initialized for project: {project_name}")
    return _langsmith_client


def get_langsmith_client() -> Optional[Client]:
    """Get the configured LangSmith client."""
    if not _langsmith_client and os.getenv("LANGSMITH_API_KEY"):
        setup_langsmith()
    return _langsmith_client


# ============================================================================
# NODE TRACING DECORATORS
# ============================================================================

def trace_node(node_name: str):
    """
    Decorator to automatically trace node execution in LangSmith.
    
    Usage:
        @trace_node("classify_question")
        async def classify_question(state: AssistantState) -> AssistantState:
            # Your logic
            return state
    
    Args:
        node_name: Name of the node to trace
    """
    def decorator(func: Callable) -> Callable:
        # Check if function is async
        import inspect
        is_async = inspect.iscoroutinefunction(func)
        
        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                client = get_langsmith_client()
                
                if client:
                    @traceable(name=node_name)
                    async def traced_call():
                        return await func(*args, **kwargs)
                    
                    return await traced_call()
                else:
                    return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                client = get_langsmith_client()
                
                if client:
                    @traceable(name=node_name)
                    def traced_call():
                        return func(*args, **kwargs)
                    
                    return traced_call()
                else:
                    return func(*args, **kwargs)
            
            return sync_wrapper
    
    return decorator


# ============================================================================
# PARAMETER EXTRACTION TRACE HELPER
# ============================================================================

class ParameterExtractionTracer:
    """
    Helps trace parameter extraction decisions for debugging and analysis.
    """
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_langsmith_client()
    
    def log_extraction(
        self,
        question: str,
        extracted_params: Dict[str, Any],
        extraction_method: str = "llm",  # "llm", "pattern", "hybrid"
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log parameter extraction decision to LangSmith.
        
        Args:
            question: Original question
            extracted_params: Extracted parameters
            extraction_method: How parameters were extracted
            confidence: Confidence score (0.0-1.0)
            metadata: Additional metadata
        """
        if not self.client:
            return
        
        try:
            self.client.log_feedback(
                run_id=os.getenv("LANGSMITH_RUN_ID"),
                key="parameter_extraction",
                score=confidence,
                feedback_source="system",
                metadata={
                    "question": question,
                    "method": extraction_method,
                    "params": extracted_params,
                    **(metadata or {}),
                }
            )
        except Exception as e:
            logger.debug(f"Failed to log parameter extraction: {e}")
    
    def log_parameter_metrics(
        self,
        params: Dict[str, Any],
        expected_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """
        Calculate and log parameter extraction metrics.
        
        Args:
            params: Extracted parameters
            expected_params: Expected parameters for comparison
            
        Returns:
            Dictionary of metrics
        """
        metrics = {
            "param_count": len(params),
            "param_types": self._count_param_types(params),
        }
        
        if expected_params:
            metrics.update(self._compare_params(params, expected_params))
        
        return metrics
    
    @staticmethod
    def _count_param_types(params: Dict[str, Any]) -> Dict[str, int]:
        """Count parameters by type."""
        type_counts = {}
        for value in params.values():
            type_name = type(value).__name__
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        return type_counts
    
    @staticmethod
    def _compare_params(
        actual: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare actual vs expected parameters."""
        actual_keys = set(k.lower() for k in actual.keys())
        expected_keys = set(k.lower() for k in expected.keys())
        
        return {
            "matching_keys": len(actual_keys & expected_keys),
            "missing_keys": len(expected_keys - actual_keys),
            "extra_keys": len(actual_keys - expected_keys),
            "key_match_rate": len(actual_keys & expected_keys) / max(len(expected_keys), 1),
        }


# ============================================================================
# ENDPOINT SELECTION TRACE HELPER
# ============================================================================

class EndpointSelectionTracer:
    """
    Helps trace endpoint selection decisions for debugging and analysis.
    """
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_langsmith_client()
    
    def log_endpoint_selection(
        self,
        question: str,
        selected_endpoint: Dict[str, Any],
        candidates: list,
        selection_method: str = "llm",  # "llm", "score", "fallback"
        confidence: float = 1.0,
    ) -> None:
        """
        Log endpoint selection decision.
        
        Args:
            question: Original question
            selected_endpoint: Selected endpoint
            candidates: All candidate endpoints considered
            selection_method: How endpoint was selected
            confidence: Confidence score
        """
        if not self.client:
            return
        
        try:
            self.client.log_feedback(
                run_id=os.getenv("LANGSMITH_RUN_ID"),
                key="endpoint_selection",
                score=confidence,
                feedback_source="system",
                metadata={
                    "question": question,
                    "selected_id": selected_endpoint.get("id"),
                    "selected_url": selected_endpoint.get("url"),
                    "method": selection_method,
                    "candidate_count": len(candidates),
                    "top_candidate_scores": [
                        c.get("score", 0) for c in candidates[:3]
                    ],
                }
            )
        except Exception as e:
            logger.debug(f"Failed to log endpoint selection: {e}")
    
    def log_selection_metrics(
        self,
        candidates: list,
        selected_id: str,
    ) -> Dict[str, Any]:
        """
        Calculate endpoint selection metrics.
        
        Args:
            candidates: All candidates with scores
            selected_id: ID of selected endpoint
            
        Returns:
            Metrics dictionary
        """
        if not candidates:
            return {}
        
        scores = [c.get("score", 0) for c in candidates]
        selected_idx = next(
            (i for i, c in enumerate(candidates) if c.get("id") == selected_id),
            -1
        )
        
        return {
            "candidate_count": len(candidates),
            "top_score": max(scores) if scores else 0,
            "bottom_score": min(scores) if scores else 0,
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "selected_rank": selected_idx + 1 if selected_idx >= 0 else -1,
            "selected_is_top": selected_idx == 0,
        }


# ============================================================================
# INTEGRATED TRACING CONTEXT
# ============================================================================

class LangSmithTraceContext:
    """
    Provides an integrated tracing context for a complete workflow.
    
    Usage:
        with LangSmithTraceContext("my_workflow") as trace:
            trace.log_input(question)
            trace.log_classification(intent, domain)
            trace.log_endpoint_selection(endpoint, candidates)
            trace.log_parameters(params)
    """
    
    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        self.client = get_langsmith_client()
        self.param_tracer = ParameterExtractionTracer(self.client)
        self.endpoint_tracer = EndpointSelectionTracer(self.client)
        self.trace_data = {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Error in trace context: {exc_val}")
    
    def log_input(self, question: str) -> None:
        """Log input question."""
        self.trace_data["question"] = question
        logger.debug(f"📝 Input: {question}")
    
    def log_classification(self, intent: str, domain: str) -> None:
        """Log classification results."""
        self.trace_data["intent"] = intent
        self.trace_data["domain"] = domain
        logger.debug(f"🏷️  Classification: intent={intent}, domain={domain}")
    
    def log_endpoint_selection(
        self,
        selected_endpoint: Dict[str, Any],
        candidates: list,
        method: str = "llm",
    ) -> None:
        """Log endpoint selection."""
        self.endpoint_tracer.log_endpoint_selection(
            self.trace_data.get("question", ""),
            selected_endpoint,
            candidates,
            method,
        )
        logger.debug(f"🎯 Selected endpoint: {selected_endpoint.get('id')}")
    
    def log_parameters(self, params: Dict[str, Any]) -> None:
        """Log extracted parameters."""
        self.trace_data["params"] = params
        logger.debug(f"📊 Parameters: {params}")
    
    def log_metrics(self, metrics: Dict[str, Any]) -> None:
        """Log additional metrics."""
        self.trace_data["metrics"] = metrics
        logger.debug(f"📈 Metrics: {json.dumps(metrics, indent=2)}")
    
    def get_trace_data(self) -> Dict[str, Any]:
        """Get all traced data."""
        return self.trace_data.copy()


# ============================================================================
# COMPARISON/BASELINE HELPERS
# ============================================================================

def compare_runs(run_id_1: str, run_id_2: str) -> Dict[str, Any]:
    """
    Compare two runs from LangSmith.
    
    Args:
        run_id_1: First run ID
        run_id_2: Second run ID
        
    Returns:
        Comparison results
    """
    client = get_langsmith_client()
    if not client:
        return {}
    
    try:
        run1 = client.read_run(run_id_1)
        run2 = client.read_run(run_id_2)
        
        return {
            "run1_id": run_id_1,
            "run2_id": run_id_2,
            "run1_duration": run1.end_time - run1.start_time if run1.end_time else None,
            "run2_duration": run2.end_time - run2.start_time if run2.end_time else None,
            "run1_error": run1.error,
            "run2_error": run2.error,
        }
    except Exception as e:
        logger.error(f"Failed to compare runs: {e}")
        return {}


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    # Setup
    setup_langsmith("endpoint_selection")
    
    # Use tracer
    param_tracer = ParameterExtractionTracer()
    endpoint_tracer = EndpointSelectionTracer()
    
    # Example: Log parameter extraction
    param_tracer.log_extraction(
        "Show me sales for March 2024",
        {"month": "March", "year": 2024},
        "llm",
        0.95
    )
    
    # Example: Log endpoint selection
    endpoint_tracer.log_endpoint_selection(
        "Show me sales for March 2024",
        {"id": "GetAllVentes", "url": "/api/ventes"},
        [
            {"id": "GetAllVentes", "score": 0.95},
            {"id": "GetAllClients", "score": 0.42},
        ],
        "llm",
        0.95
    )
    
    # Example: Use trace context
    with LangSmithTraceContext("sales_query") as trace:
        trace.log_input("Show me sales for March 2024")
        trace.log_classification("GET", "commercial")
        trace.log_endpoint_selection(
            {"id": "GetAllVentes"},
            [{"id": "GetAllVentes", "score": 0.95}],
        )
        trace.log_parameters({"month": "March", "year": 2024})
        
        print("\n✅ Trace logged:")
        print(json.dumps(trace.get_trace_data(), indent=2, default=str))
