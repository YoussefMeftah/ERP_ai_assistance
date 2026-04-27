"""
Node: Filter and process API results.

Handles:
    - Loading cached API results
    - Limiting results (first 20 records)
    - MongoDB staging for large result sets (>50 records)
    - Client-side Llama-based filtering for custom conditions
"""

import json
from pathlib import Path
from typing import Dict, Any

from state import AssistantState
from config import config
from utils.mongodb_staging import get_mongodb_staging
from utils.api_client import call_ollama_chat


def evidence_filter(state: AssistantState) -> AssistantState:
    """Filter and process cached API results.
    
    Steps:
        1. Load cached API result from call_webapi
        2. If result > 50 records, stage to MongoDB
        3. If user specified custom filters, use Llama to generate filter logic
        4. Limit returned records to 20 for evidence
        5. Compute confidence based on result quality
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with filtered_result and confidence
    """
    path_str = state.get("api_result_path", "")
    
    # Validate cached result exists
    if not path_str:
        return {
            "filtered_result": {"records": [], "count": 0},
            "confidence": 0.0,
        }
    
    path = Path(path_str)
    if not path.exists() or not path.is_file():
        return {
            "filtered_result": {"records": [], "count": 0},
            "confidence": 0.0,
        }
    
    # Load cached API result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "filtered_result": {"records": [], "count": 0},
            "confidence": 0.0,
        }
    
    # Extract records from cached format
    # Format is: {"calls": [{"raw": {"data": [...]}}], ...}
    records = []
    calls = payload.get("calls", [])
    for call in calls:
        if call.get("raw"):
            raw = call["raw"]
            if isinstance(raw, dict) and "data" in raw:
                call_records = raw["data"]
                if isinstance(call_records, list):
                    records.extend(call_records)
    
    total_count = len(records)
    
    # ========== MongoDB Staging for Large Results ==========
    mongodb_staging = get_mongodb_staging()
    if mongodb_staging.should_stage(total_count):
        collection_name = mongodb_staging.stage_results(
            collection_name="large_api_results",
            records=records,
            metadata={
                "_question": state.get("question", ""),
                "_domain": state.get("domain", ""),
                "_endpoints": payload.get("endpoints", []),
            }
        )
        if collection_name:
            # Note: In production, you could query MongoDB here
            # For now, still use first 20 records but they're also in MongoDB
            pass
    
    # ========== Client-Side Filtering with Llama ==========
    question = state.get("question", "")
    filtered_records = records
    
    # Check if question has filtering keywords
    has_filter_keywords = any(kw in question.lower() for kw in [
        "filter", "filtrer", "where", "ou", "except", "sauf",
        "greater than", "less than", ">", "<", "==", "!=",
        "contient", "contains", "ne contient pas"
    ])
    
    if has_filter_keywords and records:
        # Use Llama to generate filter logic
        system_prompt = (
            "You are a data filtering assistant for an ERP system. "
            "Based on the user's question, generate a simple JSON filter condition. "
            "Return ONLY valid Python code for filtering (e.g., 'record[\"amount\"] > 100'). "
            "Return no explanation, just the filter code."
        )
        user_prompt = (
            f"Question: {question}\n"
            f"Sample record: {json.dumps(records[0], ensure_ascii=False) if records else '{}'}\n"
            "Generate a simple Python filter expression. "
            "Example: record['status'] == 'Active' and record['amount'] > 100"
        )
        
        try:
            filter_code = call_ollama_chat(
                model=config.ollama_model_answer(),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=30,
            )
            
            # Apply filter safely
            if filter_code and filter_code.strip():
                filtered_records = []
                for record in records:
                    try:
                        # Safe evaluation context
                        eval_context = {"record": record, **record}
                        if eval(
                            filter_code,
                            {"__builtins__": {}},
                            eval_context
                        ):
                            filtered_records.append(record)
                    except Exception:
                        # Skip records that fail evaluation
                        pass
        except Exception:
            # If Llama filtering fails, just use unfiltered records
            pass
    
    # ========== Limit Results ==========
    # For AGGREGATE/STATS queries, keep more records (up to 100) for analysis
    # For simple GET queries, limit to 20 for practical evidence
    intent = state.get("intent", "GET")
    if intent in ("AGGREGATE", "REPORT", "STATS"):
        record_limit = 100
    else:
        record_limit = 20
    
    limited_records = filtered_records[:record_limit]
    
    # Count records by endpoint source
    by_endpoint: Dict[str, int] = {}
    for record in limited_records:
        endpoint_id = str(record.get("endpoint", "unknown"))
        by_endpoint[endpoint_id] = by_endpoint.get(endpoint_id, 0) + 1
    
    # ========== Confidence Scoring ==========
    confidence = 0.0
    if limited_records:
        # Base confidence if we have records
        confidence = 0.6
        
        # Boost if significant result set
        if total_count >= 5:
            confidence = min(0.85, confidence + 0.15)
        
        # Reduce if few results
        if total_count < 2:
            confidence = 0.4
    else:
        confidence = 0.2  # No results found
    
    return {
        "filtered_result": {
            "records": limited_records,
            "count": len(limited_records),
            "total_count": total_count,  # Original count before limiting
            "by_endpoint": by_endpoint,
        },
        "confidence": confidence,
    }
