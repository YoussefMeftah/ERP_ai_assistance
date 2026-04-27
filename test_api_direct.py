#!/usr/bin/env python3
"""Direct test of the ERP API with NTLM authentication."""

import requests
from requests_ntlm import HttpNtlmAuth
import json
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Test parameters
url = "https://localhost:44393/api/BlClient/GetAllClients"

print(f"Testing direct API call to: {url}")
print("=" * 80)

try:
    # Use NTLM authentication with current Windows user
    # Empty string for username/password triggers SSPI (single sign-on)
    response = requests.get(
        url,
        auth=HttpNtlmAuth('', ''),
        timeout=60,
        verify=False
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print("=" * 80)
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"Response JSON (pretty printed):")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Extract key info
            if "data" in data:
                print(f"\n{'=' * 80}")
                print(f"Total records in response: {len(data['data'])}")
                print(f"First client: {data['data'][0] if data['data'] else 'None'}")
        except json.JSONDecodeError:
            print(f"Raw Response Text:\n{response.text}")
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
