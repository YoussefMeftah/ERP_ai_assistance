#!/usr/bin/env python3
"""
Test script: Use EXACT same logic as main code for endpoint selection.

This replicates the exact flow:
1. Classify question (intent, domain)
2. Load endpoints from Swagger
3. Score endpoints (with business filter)
4. Use DeepSeek to select best endpoint + extract parameters

Usage:
    python test_endpoint_selection.py "Afficher les ventes par articles"
    python test_endpoint_selection.py "Combien de clients avons-nous?"
"""

import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from utils.endpoint_loader import load_endpoints
from nodes.endpoint_scoring import score_endpoints
from nodes.classify_question import classify_question as classify
from nodes.select_endpoint import (
    build_router_candidates_payload,
    select_best_endpoints_with_llm,
    determine_endpoint_limit,
)
from state import AssistantState


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"🔹 {title}")
    print("="*70)


def main():
    if len(sys.argv) < 2:
        print("""
Usage: python test_endpoint_selection.py "Your question here"

Examples:
  python test_endpoint_selection.py "Afficher les ventes par articles"
  python test_endpoint_selection.py "Combien de clients avons-nous?"
  python test_endpoint_selection.py "Show clients from Paris"
        """)
        return 1
    
    question = " ".join(sys.argv[1:])
    
    print("\n" + "="*70)
    print("🧪 ENDPOINT SELECTION TEST (Using Main Flow Logic)")
    print("="*70)
    print(f"\n📌 Question: {question}")
    
    # ===== STEP 1: Classify Question =====
    print_section("STEP 1: CLASSIFY QUESTION")
    state = AssistantState()
    state["question"] = question
    classify_result = classify(state)
    intent = classify_result.get("intent", "GET")
    domain = classify_result.get("domain", "general")
    
    print(f"Intent: {intent}")
    print(f"Domain: {domain}")
    
    # ===== STEP 2: Load Endpoints =====
    print_section("STEP 2: LOAD ENDPOINTS")
    endpoints = load_endpoints()
    print(f"✅ Loaded {len(endpoints)} endpoints from Swagger")
    
    # ===== STEP 3: Score & Filter Candidates =====
    print_section("STEP 3: SCORE ENDPOINTS (with business filter)")
    
    scored = score_endpoints(
        endpoints=endpoints,
        question=question,
        intent=intent,
        domain=domain,
        apply_business_filter=True,
    )
    
    print(f"Found {len(scored)} business-filtered endpoints")
    
    # If no business endpoints, retry without filter
    if not scored:
        print(f"⚠️  Retrying without business filter...")
        scored = score_endpoints(
            endpoints=endpoints,
            question=question,
            intent=intent,
            domain=domain,
            apply_business_filter=False,
        )
        print(f"Found {len(scored)} endpoints (no filter)")
    
    # Show top candidates
    if scored:
        print(f"\n🏆 Top Candidates (by score):")
        for i, ep in enumerate(scored[:5], 1):
            score = ep.get("score", 0)
            print(f"   {i}. {ep.get('id')} (score: {score})")
            print(f"      {ep.get('description')[:60]}...")
    else:
        print(f"\n❌ NO ENDPOINTS FOUND!")
        print(f"   Sample endpoints:")
        for ep in endpoints[:3]:
            print(f"   • {ep.get('id')}: {ep.get('description')[:50]}")
        return 1
    
    # ===== STEP 4: Determine endpoint limit =====
    print_section("STEP 4: DETERMINE ENDPOINT LIMIT")
    limit = determine_endpoint_limit(question, intent)
    print(f"Endpoint limit: {limit}")
    
    # ===== STEP 5: Use DeepSeek to select best endpoint(s) =====
    print_section("STEP 5: DEEPSEEK ROUTING (Select best endpoint + extract params)")
    
    print(f"Candidates passed to DeepSeek: {len(scored[:12])}")
    print(f"Router model: {config.ollama_model_router()}")
    print(f"\n📤 Calling DeepSeek...")
    
    selected_endpoints, extracted_params, error = select_best_endpoints_with_llm(
        candidates=scored,
        question=question,
        intent=intent,
        router_model=config.ollama_model_router(),
    )
    
    if error:
        print(f"❌ Error: {error}")
        return 1
    
    # ===== FINAL RESULTS =====
    print_section("FINAL RESULTS")
    
    if selected_endpoints:
        print(f"\n✅ Selected Endpoints: ({len(selected_endpoints)})")
        for ep in selected_endpoints:
            ep_id = ep.get("id")
            print(f"   • {ep_id}")
            print(f"     {ep.get('description', 'No description')[:70]}")
    else:
        print(f"\n❌ No endpoints selected by DeepSeek")
        return 1
    
    if extracted_params:
        print(f"\n📦 Extracted Parameters:")
        for param_name, value in extracted_params.items():
            print(f"   • {param_name} = '{value}'")
    else:
        print(f"\n⚠️  No parameters extracted")
    
    print("\n" + "="*70)
    print("✅ Test Complete!")
    print("="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
