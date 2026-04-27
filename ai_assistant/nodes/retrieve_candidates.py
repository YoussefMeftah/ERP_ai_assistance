"""Node: Retrieve candidate endpoints from configuration and Swagger."""

from state import AssistantState
from utils.endpoint_loader import load_endpoints
from .endpoint_scoring import score_endpoints


def retrieve_candidate_endpoints(state: AssistantState) -> AssistantState:
    """Retrieve and score endpoint candidates for the user question.
    
    Steps:
        1. Load endpoints from all sources (Swagger, JSON, overrides)
        2. Filter and score endpoints based on question
        3. Return top candidates for downstream LLM routing
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with endpoint_candidates
    """
    question = state.get("question", "")
    intent = state.get("intent", "GET")
    domain = state.get("domain", "general")
    
    # Load all available endpoints
    endpoints = load_endpoints()
    
    # Score with business filter (preferred endpoints)
    scored = score_endpoints(
        endpoints=endpoints,
        question=question,
        intent=intent,
        domain=domain,
        apply_business_filter=True,
    )
    
    # If no business endpoints found, try without filter
    if not scored:
        scored = score_endpoints(
            endpoints=endpoints,
            question=question,
            intent=intent,
            domain=domain,
            apply_business_filter=False,
        )
    
    # Return up to 12 best candidates for LLM routing
    max_candidates = 12
    return {"endpoint_candidates": scored[:max_candidates]}
