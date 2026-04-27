#!/usr/bin/env python3
"""Debug script to see what DeepSeek is actually returning for endpoint selection."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import config
from utils.endpoint_loader import load_endpoints
from utils.api_client import call_ollama_json
from nodes.endpoint_scoring import score_endpoints
from nodes.classify_question import classify_question as classify
from nodes.select_endpoint import build_router_candidates_payload
from state import AssistantState


def main():
    if len(sys.argv) < 2:
        question = "Afficher les ventes par articles"
    else:
        question = " ".join(sys.argv[1:])
    
    print(f"\n❓ Question: {question}")
    
    # Classify
    state = AssistantState()
    state["question"] = question
    result = classify(state)
    intent = result.get("intent", "GET")
    domain = result.get("domain", "general")
    
    print(f"Intent: {intent}, Domain: {domain}")
    
    # Load and score endpoints
    endpoints = load_endpoints()
    scored = score_endpoints(
        endpoints=endpoints,
        question=question,
        intent=intent,
        domain=domain,
        apply_business_filter=False,  # Don't filter
    )
    
    print(f"\n✅ Loaded {len(scored)} endpoints")
    print(f"Top candidate: {scored[0].get('id') if scored else 'NONE'}")
    
    # Build compact candidates
    compact = build_router_candidates_payload(scored[:3], 3)
    
    # Call DeepSeek
    system_prompt = (
        "You are an API endpoint router. "
        "Return JSON with 'endpoint_ids' array and 'extracted_params' object."
    )
    
    user_prompt = f"""Question: {question}
Intent: {intent}

Available Endpoints:
{json.dumps(compact, ensure_ascii=False)}

Select the best endpoint and extract parameters.
Return ONLY valid JSON with:
- endpoint_ids: array of endpoint IDs
- extracted_params: object with param names and values
"""
    
    print(f"\n📤 Calling DeepSeek...")
    response = call_ollama_json(
        model=config.ollama_model_router(),
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )
    
    print(f"\n📦 DeepSeek Response:")
    if response:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        
        print(f"\n✅ Response Structure:")
        print(f"   Has 'endpoint_ids': {'endpoint_ids' in response}")
        print(f"   Has 'endpoint_id': {'endpoint_id' in response}")
        print(f"   Has 'selected_endpoint': {'selected_endpoint' in response}")
        print(f"   Has 'extracted_params': {'extracted_params' in response}")
        
        if 'endpoint_ids' in response:
            print(f"\n   endpoint_ids: {response['endpoint_ids']}")
        if 'extracted_params' in response:
            print(f"   extracted_params: {response['extracted_params']}")
    else:
        print("❌ No response (invalid JSON)")


if __name__ == "__main__":
    main()
