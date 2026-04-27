#!/usr/bin/env python3
"""
Test script: Extract parameters from user input and select the right endpoint.

Uses DeepSeek Coder to:
1. Extract parameters from user question
2. Choose the best matching endpoint

Usage:
    python test_endpoint_selection.py "Afficher les ventes par articles"
    python test_endpoint_selection.py "Combien de clients avons-nous?"
    python test_endpoint_selection.py "Show clients from Paris"
"""

import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from utils.endpoint_loader import load_endpoints
from utils.api_client import call_ollama_json
from nodes.endpoint_scoring import score_endpoints
from nodes.classify_question import classify_question as classify
from state import AssistantState


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"🔹 {title}")
    print("="*70)


def extract_parameters_with_deepseek(question: str, endpoints: list) -> dict:
    """Use DeepSeek to extract parameters from user question.
    
    Args:
        question: User's natural language question
        endpoints: Available endpoints with their parameter hints
    
    Returns:
        Dict with extracted parameters
    """
    print_section("PARAMETER EXTRACTION (DeepSeek Coder)")
    
    # Build endpoint descriptions for DeepSeek
    endpoint_descriptions = []
    for ep in endpoints[:5]:  # Use top 5 candidates
        endpoint_descriptions.append({
            "id": ep.get("id"),
            "path": ep.get("url"),
            "description": ep.get("description"),
            "requiredParameters": ep.get("requiredParameters", []),
            "queryParameters": ep.get("queryParameters", []),
            "parameterMetadata": ep.get("parameterMetadata", {})
        })
    
    system_prompt = """You are an expert at extracting parameters from natural language questions for API calls.

Your task: Analyze the user's question and extract all relevant parameters.

For each parameter, determine:
1. Parameter name (as used in the API)
2. Extracted value from the question
3. Data type (string, integer, date, etc.)
4. Confidence level (high/medium/low)

IMPORTANT NOTES:
- For dates: Try to extract explicit dates or date ranges. If none found, return "auto" for system to apply defaults
- For IDs/codes: Look for patterns like "id 123", "client ABC", "code XYZ"
- For text values: Extract exact values mentioned
- Be case-sensitive when extracting codes or IDs

Return as JSON with this structure:
{
  "extracted_parameters": {
    "param_name": {
      "value": "extracted_value",
      "type": "string|integer|date",
      "confidence": "high|medium|low",
      "reason": "why this was extracted"
    }
  },
  "parameter_summary": "Brief summary of extracted params"
}"""

    user_prompt = f"""Question: {question}

Available endpoints and their parameters:
{json.dumps(endpoint_descriptions, indent=2, ensure_ascii=False)}

Extract all parameters that would be needed to answer this question.
Return ONLY valid JSON, no explanations."""

    try:
        print(f"❓ Question: {question}")
        print(f"\n📤 Calling DeepSeek...")
        
        result = call_ollama_json(
            model=config.ollama_model_router(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout=config.ollama_router_timeout_seconds()
        )
        
        if result:
            print(f"\n✅ Extracted Parameters:")
            params = result.get("extracted_parameters", {})
            for param_name, details in params.items():
                value = details.get("value")
                confidence = details.get("confidence")
                print(f"   • {param_name}: '{value}' ({confidence} confidence)")
                if details.get("reason"):
                    print(f"     → {details['reason']}")
            
            if result.get("parameter_summary"):
                print(f"\n📝 Summary: {result['parameter_summary']}")
            
            return result.get("extracted_parameters", {})
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return {}


def select_endpoint_with_deepseek(question: str, endpoints: list, extracted_params: dict) -> dict:
    """Use DeepSeek to select the best endpoint for the question.
    
    Args:
        question: User's question
        endpoints: Available endpoints
        extracted_params: Parameters extracted from question
    
    Returns:
        Dict with selected endpoint and reasoning
    """
    print_section("ENDPOINT SELECTION (DeepSeek Coder)")
    
    # Prepare endpoint options
    endpoint_options = []
    for ep in endpoints[:8]:  # Show top 8 options
        endpoint_options.append({
            "id": ep.get("id"),
            "path": ep.get("url"),
            "description": ep.get("description"),
            "keywords": ep.get("keywords", []),
            "requiredParameters": ep.get("requiredParameters", []),
            "intent": ep.get("intent", "GET")
        })
    
    system_prompt = """You are an expert API endpoint selector.

Your task: Given a user question and available endpoints, select the BEST matching endpoint.

Consider:
1. Question intent and keywords
2. Endpoint description and keywords
3. Required vs available parameters
4. API intent (GET, AGGREGATE, etc.)

Return JSON with:
{
  "selected_endpoint": {
    "id": "endpoint_id",
    "confidence": 0.0-1.0,
    "reasoning": "why this endpoint was selected",
    "parameter_fit": "high/medium/low - how well parameters match"
  },
  "alternatives": [
    {
      "id": "alternative_endpoint_id",
      "confidence": 0.0-1.0,
      "reason": "why this could work"
    }
  ]
}"""

    user_prompt = f"""Question: {question}

Extracted Parameters:
{json.dumps(extracted_params, indent=2, ensure_ascii=False)}

Available Endpoints:
{json.dumps(endpoint_options, indent=2, ensure_ascii=False)}

Select the best endpoint for this question.
Return ONLY valid JSON."""

    try:
        print(f"❓ Question: {question}")
        print(f"📊 Candidates: {len(endpoint_options)} endpoints")
        print(f"🔍 Extracted Parameters: {len(extracted_params)}")
        
        print(f"\n📤 Calling DeepSeek...")
        
        result = call_ollama_json(
            model=config.ollama_model_router(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout=config.ollama_router_timeout_seconds()
        )
        
        if result and result.get("selected_endpoint"):
            selected = result["selected_endpoint"]
            print(f"\n✅ Selected Endpoint: {selected.get('id')}")
            print(f"   Confidence: {selected.get('confidence', 0):.0%}")
            print(f"   Parameter Fit: {selected.get('parameter_fit', 'unknown')}")
            print(f"   Reasoning: {selected.get('reasoning', 'N/A')}")
            
            # Show alternatives
            alternatives = result.get("alternatives", [])
            if alternatives:
                print(f"\n🔄 Alternatives:")
                for alt in alternatives[:3]:
                    print(f"   • {alt.get('id')}: {alt.get('confidence', 0):.0%} - {alt.get('reason')}")
            
            return result.get("selected_endpoint", {})
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return {}


def score_candidates(question: str, endpoints: list) -> list:
    """Score endpoints using keyword matching (for comparison).
    
    This is the baseline scoring before DeepSeek selection.
    """
    print_section("CANDIDATE SCORING (Baseline - Keyword Match)")
    
    # Classify question first
    state = AssistantState()
    state["question"] = question
    classify_result = classify(state)
    intent = classify_result.get("intent", "GET")
    domain = classify_result.get("domain", "general")
    
    print(f"Intent: {intent}")
    print(f"Domain: {domain}")
    
    # Score endpoints
    scored = score_endpoints(
        endpoints=endpoints,
        question=question,
        intent=intent,
        domain=domain,
        apply_business_filter=True
    )
    
    print(f"\n🏆 Top Candidates (by keyword score):")
    for i, ep in enumerate(scored[:5], 1):
        score = ep.get("score", 0)
        print(f"   {i}. {ep.get('id')} (score: {score:.2f})")
        print(f"      {ep.get('description')[:60]}...")
    
    return scored


def main():
    if len(sys.argv) < 2:
        print("""
Usage: python test_endpoint_selection.py "Your question here"

Examples:
  python test_endpoint_selection.py "Afficher les ventes par articles"
  python test_endpoint_selection.py "Combien de clients avons-nous?"
  python test_endpoint_selection.py "Show clients from Paris"
  python test_endpoint_selection.py "How many sales in 2024?"
        """)
        return 1
    
    question = " ".join(sys.argv[1:])
    
    print("\n" + "="*70)
    print("🧪 ENDPOINT SELECTION TEST")
    print("="*70)
    print(f"\n📌 Question: {question}")
    
    # Load all endpoints
    print("\n🔄 Loading endpoints...")
    endpoints = load_endpoints()
    print(f"✅ Loaded {len(endpoints)} endpoints")
    
    # Step 1: Score candidates (baseline)
    scored_endpoints = score_candidates(question, endpoints)
    
    # Step 2: Extract parameters with DeepSeek
    extracted_params = extract_parameters_with_deepseek(question, scored_endpoints)
    
    # Step 3: Select endpoint with DeepSeek
    selected = select_endpoint_with_deepseek(question, scored_endpoints, extracted_params)
    
    # Final Summary
    print_section("FINAL RESULT")
    print(f"\n✨ Selected Endpoint: {selected.get('id', 'NONE')}")
    print(f"   Confidence: {selected.get('confidence', 0):.0%}")
    
    if extracted_params:
        print(f"\n📦 Parameters to Use:")
        for param, details in extracted_params.items():
            print(f"   • {param} = '{details.get('value')}' ({details.get('type')})")
    
    print("\n" + "="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
