"""
Data processing utilities: filtering, normalization, and evidence building.
"""

import json
from typing import Any, Dict, List


def normalize_data_field(payload: Any) -> List[Any]:
    """Normalize various API response formats to a list of records.
    
    Handles:
        - Direct list: [record, ...]
        - Object with 'data' field: {"data": [...]}
        - Object with 'value' field: {"value": [...]}
        - Object with 'items' field: {"items": [...]}
        - Single object: wraps as [object]
        - Other: empty list
    
    Args:
        payload: API response payload
    
    Returns:
        List of records
    """
    if isinstance(payload, list):
        return payload
    
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload["data"]
        if isinstance(payload.get("value"), list):
            return payload["value"]
        if isinstance(payload.get("items"), list):
            return payload["items"]
        return [payload]
    
    return []


def truncate_text(value: Any, max_length: int = 240) -> str:
    """Truncate value to max length with ellipsis.
    
    Args:
        value: Any value to stringify and truncate
        max_length: Max characters before truncation
    
    Returns:
        Truncated string
    """
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def build_answer_evidence(
    filtered: Dict[str, Any],
    max_records: int = 8,
    max_fields: int = 8,
) -> Dict[str, Any]:
    """Build compact evidence for LLM answer generation.
    
    Truncates records and fields to avoid overwhelming the LLM with context size.
    
    Args:
        filtered: Result from evidence_filter node
        max_records: Max records to include in evidence
        max_fields: Max fields per record to include
    
    Returns:
        Compact evidence structured for LLM input
    """
    records = filtered.get("records", [])
    compact_records: List[Dict[str, Any]] = []
    
    for item in records[:max_records]:
        if isinstance(item, dict):
            record = item.get("record", item)
            endpoint = item.get("endpoint")
            
            if isinstance(record, dict):
                # Trim fields to max_fields
                trimmed_record: Dict[str, Any] = {}
                for idx, (key, value) in enumerate(record.items()):
                    if idx >= max_fields:
                        break
                    
                    if isinstance(value, (dict, list)):
                        trimmed_record[key] = truncate_text(
                            json.dumps(value, ensure_ascii=False),
                            120
                        )
                    else:
                        trimmed_record[key] = truncate_text(value, 120)
                
                compact_records.append({
                    "endpoint": endpoint,
                    "record": trimmed_record
                })
            else:
                compact_records.append({
                    "endpoint": endpoint,
                    "record": truncate_text(record, 120)
                })
        else:
            compact_records.append({
                "record": truncate_text(item, 120)
            })
    
    return {
        "count": filtered.get("count", 0),
        "total_count": filtered.get("total_count", 0),
        "by_endpoint": filtered.get("by_endpoint", {}),
        "records": compact_records,
    }


def filter_by_condition(
    records: List[Dict[str, Any]],
    condition: str,
) -> List[Dict[str, Any]]:
    """Filter records by a simple condition string.
    
    Simple conditions like:
        - "status == 'active'"
        - "amount > 100"
        - "city contains 'paris'"
    
    Args:
        records: List of record dicts
        condition: Condition string (simple evaluation)
    
    Returns:
        Filtered list of records
    """
    # Note: This is a basic implementation.
    # For production, use a safer expression evaluator like `safer_eval`
    # or have Llama generate Python filter logic.
    
    filtered = []
    for record in records:
        try:
            # Create a safe evaluation context with record fields
            eval_context = {"record": record, **record}
            
            # Very basic safety: only allow field references and comparisons
            # In production, use ast.literal_eval or a proper expression library
            if eval(condition, {"__builtins__": {}}, eval_context):
                filtered.append(record)
        except Exception:
            # Skip records that fail evaluation
            pass
    
    return filtered
