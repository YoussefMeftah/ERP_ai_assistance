"""Node: Select best endpoint(s) using DeepSeek routing or score-based fallback."""

from typing import Optional, Dict, Any, List
import json
from state import AssistantState
from config import config
from utils.api_client import call_ollama_json
from utils.text_utils import extract_simple_params


def build_router_candidates_payload(
    candidates: List[Dict[str, Any]],
    limit: int
) -> List[Dict[str, Any]]:
    """Build compact candidate list for LLM routing with parameter hints.
    
    Includes rich parameter information to help LLM understand what's needed.
    
    Args:
        candidates: Full endpoint candidates
        limit: Max candidates to include
    
    Returns:
        Compact representation with parameter hints
    """
    from utils.data_processing import truncate_text
    
    compact: List[Dict[str, Any]] = []
    for candidate in candidates[:limit]:
        # Build detailed parameter information for LLM
        param_metadata = candidate.get("parameterMetadata", {})
        
        # Format required parameters with full details
        required_params = []
        for param_name in param_metadata.get("required", []):
            detailed = param_metadata.get("detailed", {}).get(param_name, {})
            param_type = detailed.get("type", "string")
            param_desc = detailed.get("description", "")
            param_in = detailed.get("in", "query")
            
            param_info = {
                "name": param_name,
                "type": param_type,
                "location": param_in,
                "required": True
            }
            if param_desc:
                param_info["description"] = param_desc[:80]
            if "example" in detailed:
                param_info["example"] = detailed["example"]
            required_params.append(param_info)
        
        # Format optional parameters (limit to 3 to save tokens)
        optional_params = []
        for param_name in param_metadata.get("optional", [])[:3]:
            detailed = param_metadata.get("detailed", {}).get(param_name, {})
            param_type = detailed.get("type", "string")
            param_desc = detailed.get("description", "")
            
            param_info = {
                "name": param_name,
                "type": param_type,
                "required": False
            }
            if param_desc:
                param_info["description"] = param_desc[:60]
            optional_params.append(param_info)
        
        compact.append({
            "id": candidate.get("id"),
            "url": candidate.get("url"),
            "intent": candidate.get("intent"),
            "description": truncate_text(candidate.get("description", ""), 140),
            "role": candidate.get("role", "general"),
            "tags": candidate.get("tags", [])[:4],
            "score": candidate.get("score", 0),
            "parameters": {
                "required": required_params,
                "optional": optional_params,
            },
        })
    return compact


def determine_endpoint_limit(question: str, intent: str) -> int:
    """Determine how many endpoints should be called.
    
    Uses logic:
        - Multi-endpoint markers (e.g., "compare", "et") -> up to 3
        - AGGREGATE without markers -> 1
        - Default -> 1
    
    Args:
        question: User question
        intent: Classified intent
    
    Returns:
        Number of endpoints to select
    """
    q = question.lower()
    
    # Explicit multi-endpoint markers
    multi_markers = [
        " et ", " avec ", " ainsi que ",
        " compare ", " comparaison ",
        " resume ", " résumé ",
        " tableau de bord ", " dashboard ",
        " situation ", " synthese ", " synthèse ",
    ]
    
    if any(marker in f" {q} " for marker in multi_markers):
        return 3
    
    # AGGREGATE queries: use only 1 (no comparison)
    if intent == "AGGREGATE":
        return 1
    
    return 1


def select_best_endpoints_with_llm(
    candidates: List[Dict[str, Any]],
    question: str,
    intent: str,
    router_model: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any], Optional[str]]:
    """Use DeepSeek LLM to select best endpoint(s).
    
    Args:
        candidates: Available endpoints
        question: User question
        intent: Classified intent
        router_model: LLM model to use (deepseek-coder usually)
    
    Returns:
        (selected_endpoints, extracted_params, error_message)
    """
    if not candidates:
        return [], {}, None
    
    limit = min(determine_endpoint_limit(question, intent), len(candidates))
    llm_candidate_limit = min(
        len(candidates),
        config.router_candidate_limit()
    )
    
    extracted_params: Dict[str, Any] = {}
    
    system_prompt = (
        "You are the primary endpoint router for an ERP API. "
        "Your task: (1) Choose the best endpoint(s) and (2) Extract parameters from the question.\n\n"
        "ENDPOINT SELECTION:\n"
        "- Prefer business list/report/statistics endpoints over technical, test, auth, or utility endpoints\n"
        "- Look for endpoints like GetAll, OData lists, stats, reports, and business routes that match the question\n"
        "- Choose only 1-2 endpoints unless the question explicitly compares or analyzes multiple datasets\n\n"
        "PARAMETER EXTRACTION:\n"
        "- Each endpoint shows required and optional parameters with type information\n"
        "- REQUIRED parameters: Must extract from question. Look for values matching the type (date, id, string, etc)\n"
        "- OPTIONAL parameters: Extract if mentioned in question, otherwise omit\n"
        "- Match parameter names EXACTLY as shown (case-sensitive)\n"
        "- If a required parameter is missing from the question, use context to infer a smart default\n"
        "- For date parameters: extract dates, date ranges, or months from question\n"
        "- For ID parameters: extract business IDs (client codes, product codes, etc)\n"
        "- For string parameters: extract exact values mentioned in the question\n\n"
        "RESPONSE FORMAT:\n"
        "Return ONLY valid JSON with fields:\n"
        '  - "endpoint_ids": array of chosen endpoint IDs\n'
        '  - "extracted_params": object mapping parameter names to extracted values\n'
        '  - "reasoning": brief explanation of choices'
    )
    
    compact_candidates = build_router_candidates_payload(candidates, llm_candidate_limit)
    
    # Build a detailed parameter reference for the prompt
    param_reference = "ENDPOINT PARAMETER DETAILS:\n\n"
    for i, candidate in enumerate(compact_candidates, 1):
        param_reference += f"{i}. [{candidate['id']}] {candidate['url']}\n"
        
        required = candidate.get("parameters", {}).get("required", [])
        if required:
            param_reference += "   REQUIRED:\n"
            for p in required:
                param_reference += f"     - {p['name']} ({p['type']}, in {p['location']})"
                if "description" in p:
                    param_reference += f": {p['description']}"
                if "example" in p:
                    param_reference += f" [example: {p['example']}]"
                param_reference += "\n"
        
        optional = candidate.get("parameters", {}).get("optional", [])
        if optional:
            param_reference += "   OPTIONAL:\n"
            for p in optional:
                param_reference += f"     - {p['name']} ({p['type']})"
                if "description" in p:
                    param_reference += f": {p['description']}"
                param_reference += "\n"
        param_reference += "\n"
    
    user_prompt = (
        f"Question: {question}\n"
        f"Intent: {intent}\n\n"
        f"{param_reference}\n"
        f"Available Endpoints: {json.dumps(compact_candidates, ensure_ascii=False)}\n\n"
        "Task:\n"
        "1. Analyze the question and intent\n"
        "2. Examine the endpoint parameter requirements above\n"
        "3. Select the endpoint(s) that best match the question\n"
        "4. Extract ALL required parameters from the question using the reference above\n"
        "5. Return the JSON response with endpoint_ids and extracted_params"
    )
    
    try:
        llm_choice = call_ollama_json(router_model, system_prompt, user_prompt)
        
        if not llm_choice:
            print(f"[DEBUG] ⚠️  DeepSeek returned empty/invalid JSON")
            # Fallback: use top candidate by score
            if candidates:
                top = candidates[0]
                print(f"[DEBUG] Fallback: Using top candidate by score: {top.get('id')}")
                return [top], extracted_params, None
            return None, extracted_params, "DeepSeek returned invalid JSON and no fallback candidates"
        
        print(f"[DEBUG] DeepSeek response: {json.dumps(llm_choice, ensure_ascii=False)[:200]}")
        
        # Log DeepSeek's reasoning if available
        if "reasoning" in llm_choice:
            print(f"[DEBUG] DeepSeek Reasoning: {llm_choice.get('reasoning')}")
        
        llm_params = llm_choice.get("extracted_params", {})
        if isinstance(llm_params, dict):
            extracted_params.update(llm_params)
            if llm_params:
                print(f"[DEBUG] Extracted Parameters: {json.dumps(llm_params, ensure_ascii=False)}")
        
        # Try endpoint_ids array first
        endpoint_ids = llm_choice.get("endpoint_ids")
        if isinstance(endpoint_ids, list):
            chosen_ids = [str(eid) for eid in endpoint_ids if eid]
            chosen = [c for c in candidates if str(c.get("id")) in chosen_ids]
            if chosen:
                print(f"[DEBUG] DeepSeek Selected Endpoints: {chosen_ids}")
                return chosen[:limit], extracted_params, None
        
        # Fallback to single endpoint_id
        endpoint_id = llm_choice.get("endpoint_id")
        if endpoint_id:
            chosen = next(
                (c for c in candidates if c.get("id") == endpoint_id),
                None
            )
            if chosen:
                print(f"[DEBUG] DeepSeek Selected Endpoint: {endpoint_id}")
                return [chosen], extracted_params, None
        
        # Fallback: check for "selected_endpoint" (common field name)
        selected = llm_choice.get("selected_endpoint")
        if selected and isinstance(selected, dict):
            selected_id = selected.get("id")
            if selected_id:
                chosen = next(
                    (c for c in candidates if c.get("id") == selected_id),
                    None
                )
                if chosen:
                    print(f"[DEBUG] DeepSeek Selected via 'selected_endpoint': {selected_id}")
                    return [chosen], extracted_params, None
        
        # Final fallback: use top candidate
        print(f"[DEBUG] ⚠️  No valid endpoint_ids found in response. Using top candidate by score.")
        if candidates:
            top = candidates[0]
            print(f"[DEBUG] Fallback endpoint: {top.get('id')}")
            return [top], extracted_params, None
            
    except Exception as exc:
        return None, extracted_params, f"DeepSeek routing failed: {exc}"
    
    # Nothing selected from LLM
    return None, extracted_params, "DeepSeek did not select valid endpoints"


def select_endpoint_and_params(state: AssistantState) -> AssistantState:
    """Select best endpoint(s) and extract parameters.
    
    Flow:
        1. Try DeepSeek LLM routing first
        2. Fall back to score-based selection if LLM fails
        3. Extract parameters from question
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with selected endpoints and parameters
    """
    candidates = state.get("endpoint_candidates", [])
    errors = state.get("errors", []).copy()
    
    # Extract parameters from question
    params = extract_simple_params(state.get("question", ""))
    
    # Fallback: highest-scored endpoint
    fallback_selected = candidates[0] if candidates else None
    if fallback_selected is None:
        errors.append("No endpoint candidate matched the question.")
    
    # Try DeepSeek routing
    router_model = config.ollama_model_router()
    selected_endpoints, llm_params, router_error = select_best_endpoints_with_llm(
        candidates=candidates,
        question=state.get("question", ""),
        intent=state.get("intent", "GET"),
        router_model=router_model,
    )
    
    # If LLM routing failed or returned None, use score-based fallback
    if selected_endpoints is None:
        if router_error:
            errors.append(router_error)
        # Use top-scored endpoints
        limit = determine_endpoint_limit(
            state.get("question", ""),
            state.get("intent", "GET")
        )
        selected_endpoints = candidates[:limit]
    
    # Merge LLM-extracted parameters
    if isinstance(llm_params, dict):
        params.update(llm_params)
    
    selected = selected_endpoints[0] if selected_endpoints else fallback_selected
    
    return {
        "selected_endpoints": selected_endpoints or [],
        "selected_endpoint": selected,
        "extracted_params": params,
        "errors": errors,
    }
