#!/usr/bin/env python3
"""Quick test to verify dataset loading works"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from langsmith_evaluation import TEST_CASES

print(f"\n✅ Successfully loaded {len(TEST_CASES)} test cases from api_test_evaluation.json")
print(f"\nFirst test case:")
print(f"  Prompt: {TEST_CASES[0]['input']['question']}")
print(f"  Expected Endpoint: {TEST_CASES[0]['expected_output']['endpoint']}")
print(f"  Expected Params: {TEST_CASES[0]['expected_output']['extracted_params']}")
print(f"\nLast test case:")
print(f"  Prompt: {TEST_CASES[-1]['input']['question']}")
print(f"  Expected Endpoint: {TEST_CASES[-1]['expected_output']['endpoint']}")
print(f"  Expected Params: {TEST_CASES[-1]['expected_output']['extracted_params']}")

# Count by endpoint
endpoints = {}
for case in TEST_CASES:
    ep = case['expected_output']['endpoint']
    endpoints[ep] = endpoints.get(ep, 0) + 1

print(f"\n📊 Test cases by endpoint:")
for ep, count in sorted(endpoints.items()):
    print(f"  {ep}: {count} cases")

print(f"\n✅ All datasets ready for LangSmith evaluation!")
