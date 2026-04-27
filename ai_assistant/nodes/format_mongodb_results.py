"""Node: Format MongoDB query results into a human-readable answer."""

import json
from typing import Any, Dict
from state import AssistantState


def format_mongodb_results(state: AssistantState) -> AssistantState:
    """Format MongoDB query results into a plain text answer.
    
    Receives:
        - query_results: List of documents from MongoDB aggregation
        - question: Original user question
        - result_count: Number of results
    
    Returns:
        - answer: Formatted text answer
    """
    query_results = state.get("query_results", [])
    question = state.get("question", "")
    result_count = state.get("result_count", 0)
    errors = state.get("errors", []).copy()
    
    # If no results, return empty answer with note
    if not query_results or result_count == 0:
        state["answer"] = "No results found."
        state["confidence"] = 0.3
        return state
    
    # Build answer from results
    try:
        answer_lines = []
        
        # Add result count
        if result_count == 1:
            answer_lines.append("Found 1 result:")
        else:
            answer_lines.append(f"Found {result_count} results:")
        
        answer_lines.append("")
        
        # Format each result
        for i, doc in enumerate(query_results, 1):
            if isinstance(doc, dict):
                # Simple key-value formatting
                for key, value in doc.items():
                    # Handle MongoDB's _id field specially (from $group _id)
                    if key == "_id":
                        display_key = "Item/Group"
                        formatted_value = str(value)
                    elif isinstance(value, (int, float)):
                        if isinstance(value, float):
                            formatted_value = f"{value:.2f}"
                        else:
                            formatted_value = str(value)
                        # Convert snake_case to Title Case
                        display_key = key.replace("_", " ").title()
                    else:
                        formatted_value = str(value)
                        display_key = key.replace("_", " ").title()
                    
                    answer_lines.append(f"  {display_key}: {formatted_value}")
                
                if i < result_count:
                    answer_lines.append("")
            else:
                answer_lines.append(f"  {str(doc)}")
        
        answer = "\n".join(answer_lines)
        state["answer"] = answer
        
        # Set confidence based on results
        if result_count > 0:
            state["confidence"] = 0.85
        else:
            state["confidence"] = 0.5
            
    except Exception as e:
        errors.append(f"Error formatting MongoDB results: {e}")
        state["answer"] = f"Retrieved {result_count} results but formatting failed."
        state["confidence"] = 0.3
    
    state["errors"] = errors
    return state
