"""Node: Generate natural language answer from filtered data."""

import json
from state import AssistantState
from config import config
from utils.api_client import call_ollama_chat
from utils.data_processing import build_answer_evidence


def answer_generation(state: AssistantState) -> AssistantState:
    """Generate human-friendly answer from filtered API results using Llama LLM.
    
    Flow:
        1. Build compact evidence from filtered results
        2. Call Llama with system/user prompts
        3. Fallback to template-based answer if Llama unavailable
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with answer
    """
    question = state.get("question", "")
    selected = state.get("selected_endpoint")
    selected_endpoints = state.get("selected_endpoints", [])
    filtered = state.get("filtered_result", {})
    errors = state.get("errors", []).copy()
    intent = state.get("intent", "GET")
    
    records = filtered.get("records", [])
    
    # Determine evidence size based on intent
    # AGGREGATE/STATS queries need all/most records for proper analysis
    # GET queries only need a sample for context
    if intent in ("AGGREGATE", "REPORT", "STATS"):
        max_evidence_records = 100  # Show all for aggregates
    else:
        max_evidence_records = 20   # Sample for simple gets
    
    # Build compact evidence for LLM input
    compact_evidence = build_answer_evidence(filtered, max_records=max_evidence_records, max_fields=10)
    
    # Define fallback answer template
    def build_fallback_answer() -> str:
        endpoint_ids = [str(ep.get("id")) for ep in selected_endpoints] if selected_endpoints else []
        
        if records:
            # Use total_count if available, otherwise use count
            total = filtered.get('total_count', filtered.get('count', 0))
            return (
                f"J'ai trouvé {total} enregistrements "
                f"via {', '.join(endpoint_ids) if endpoint_ids else 'les endpoints sélectionnés'}. "
                "Les données filtrées sont affichées ci-dessous."
            )
        
        if state.get("errors"):
            return (
                "Je n'ai pas pu produire une réponse complète. "
                "Des erreurs d'appel API ou de génération se sont produites. "
                "Veuillez vérifier les endpoints sélectionnés et les paramètres."
            )
        
        return (
            "Je n'ai pas trouvé de données suffisantes pour répondre à cette question."
        )
    
    # Try Llama answer generation
    model = config.ollama_model_answer()
    system_prompt = (
        "You are an ERP business analyst. Analyze the provided data records and answer the user question directly. "
        "CRITICAL: Answer ONLY from the provided evidence/records. "
        "Summarize key data points, totals, trends, and patterns from the records. "
        "Present numbers, statistics, and calculations based on the actual data provided. "
        "If asked 'afficher/display/show', list or summarize the relevant records with their key fields. "
        "Be specific with numbers, dates, and values - do not give generic advice. "
        "French: Analysez les données et répondez directement à la question de l'utilisateur."
    )
    
    user_prompt = (
        f"Question: {question}\n"
        f"Endpoint: {selected.get('id', 'Unknown') if selected else 'Unknown'}\n"
        f"Total records available: {filtered.get('total_count', 0)}\n"
        f"Records provided for analysis: {len(records)}\n"
        f"\n{json.dumps(compact_evidence, ensure_ascii=False)}\n"
        f"\nAnalyze the above data and provide a direct answer to the question. "
        f"Include relevant statistics, totals, and data points from the records."
    )
    
    answer = None
    try:
        answer = call_ollama_chat(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception as exc:
        errors.append(f"Llama answer generation failed: {exc}")
        answer = None
    
    # Use fallback if LLM failed
    if not answer:
        answer = build_fallback_answer()
    
    return {"answer": answer, "errors": errors}
