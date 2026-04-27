"""Node: Execute MongoDB aggregation pipeline and return results."""

import json
from typing import Dict, Any, List
from state import AssistantState
from config import config
from utils.mongodb_staging import connect_mongodb


def execute_mongodb_query(state: AssistantState) -> AssistantState:
    """Execute the generated MongoDB aggregation pipeline and return results.
    
    Receives:
        - mongodb_query: Aggregation pipeline (from Llama query generator)
        - collection_name: MongoDB collection to query
        - question: Original user question (for logging)
    
    Returns:
        - query_results: List of documents returned from MongoDB
        - result_count: Number of results
    """
    mongodb_query = state.get("mongodb_query")
    collection_name = state.get("collection_name", "api_results")
    question = state.get("question", "")
    errors = state.get("errors", []).copy()
    
    state["query_results"] = []
    state["result_count"] = 0
    
    if not mongodb_query:
        errors.append("No MongoDB query provided to execute")
        state["errors"] = errors
        return state
    
    if not isinstance(mongodb_query, list):
        errors.append("MongoDB query must be an aggregation pipeline (list)")
        state["errors"] = errors
        return state
    
    try:
        # Connect to MongoDB
        db = connect_mongodb()
        
        if db is None:
            errors.append("Failed to connect to MongoDB")
            state["errors"] = errors
            return state
        
        collection = db[collection_name]
        
        # Debug: Show query execution
        print(f"\n[DEBUG] ===== MONGODB QUERY EXECUTION =====")
        print(f"[DEBUG] Collection: {collection_name}")
        print(f"[DEBUG] Pipeline stages: {len(mongodb_query)}")
        print(f"[DEBUG] Executing aggregation pipeline...")
        
        # Execute aggregation pipeline
        results = list(collection.aggregate(mongodb_query))
        
        print(f"[DEBUG] Query returned {len(results)} results")
        if len(results) > 0:
            print(f"[DEBUG] First result sample:")
            print(json.dumps(results[0], indent=2, default=str)[:500])
        print(f"[DEBUG] ========================================\n")
        
        # Convert ObjectId to string for JSON serialization
        for result in results:
            if "_id" in result and hasattr(result["_id"], "hex"):
                result["_id"] = str(result["_id"])
        
        state["query_results"] = results
        state["result_count"] = len(results)
        
        # Log query execution for debugging
        import logging
        logging.info(
            f"MongoDB Query executed successfully\n"
            f"Question: {question}\n"
            f"Collection: {collection_name}\n"
            f"Results: {len(results)} documents\n"
            f"Query: {json.dumps(mongodb_query, indent=2)}"
        )
        
    except Exception as e:
        errors.append(f"MongoDB query execution failed: {e}")
        state["query_results"] = []
        state["result_count"] = 0
    
    state["errors"] = errors
    return state
