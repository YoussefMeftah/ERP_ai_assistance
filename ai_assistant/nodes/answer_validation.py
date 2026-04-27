"""Node: Validate answer quality and adjust confidence."""

from state import AssistantState


def answer_validation(state: AssistantState) -> AssistantState:
    """Validate answer quality and adjust confidence score.
    
    Heuristics:
        - If answer contains negative indicators (could not, unavailable) -> lower confidence
        - If good data was found (count > 0) -> raise confidence to 0.75+
        - If no data found -> lower confidence
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with adjusted confidence
    """
    answer = state.get("answer", "")
    confidence = state.get("confidence", 0.5)
    filtered = state.get("filtered_result", {})
    
    # Check for negative indicators in answer
    negative_phrases = [
        "could not",
        "pouvoir pas",
        "n'ai pas trouvé",
        "unavailable",
        "indisponible",
        "erreur",
        "error",
        "failed",
        "échoué",
    ]
    
    has_negative = any(phrase in answer.lower() for phrase in negative_phrases)
    if has_negative:
        confidence = min(confidence, 0.3)
    
    # Check result quality
    result_count = filtered.get("count", 0)
    if result_count > 0:
        # Good results found
        confidence = max(confidence, 0.75)
    elif result_count == 0:
        # No results - lower confidence
        confidence = min(confidence, 0.4)
    
    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, confidence))
    
    return {"confidence": confidence}
