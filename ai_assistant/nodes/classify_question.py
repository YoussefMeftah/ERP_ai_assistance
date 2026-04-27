"""Node: Classify question intent and domain."""

from state import AssistantState
from utils.text_utils import infer_domain_from_question, contains_any


def classify_question(state: AssistantState) -> AssistantState:
    """Classify user question to determine intent and business domain.
    
    Intent: GET (simple retrieval), AGGREGATE (statistics/reports), FILTER (filtering)
    Domain: commercial, stock, finance, rh, achat, general
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with intent and domain
    """
    question = state.get("question", "")
    q = question.lower()
    
    # Determine intent from keywords
    if contains_any(q, ["stat", "top", "chiffre", "total", "vente", "ventes", "rapport"]):
        intent = "AGGREGATE"
    elif contains_any(q, ["filtre", "ou", "where", "condition"]):
        intent = "FILTER"
    else:
        intent = "GET"
    
    # Infer domain from question
    domain = infer_domain_from_question(question)
    
    return {
        "intent": intent,
        "domain": domain,
    }
