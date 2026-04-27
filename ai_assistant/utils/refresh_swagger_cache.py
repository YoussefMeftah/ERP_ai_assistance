#!/usr/bin/env python3
"""CLI tool to refresh Swagger cache from live API.

Usage:
    python utils/refresh_swagger_cache.py          # Refresh from default API URLs
    python utils/refresh_swagger_cache.py -v       # Verbose output
    python utils/refresh_swagger_cache.py -u <url> # Use custom API URL
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent dir to path (handle running from utils/ or ai_assistant/ dirs)
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Change to ai_assistant directory if needed
os.chdir(str(parent_dir))

from config import config
from utils.endpoint_loader import refresh_swagger_cache, load_swagger_generated_endpoints


def main():
    parser = argparse.ArgumentParser(
        description="Refresh Swagger cache from live ERP API"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "-s", "--show",
        action="store_true",
        help="Show endpoints after refresh"
    )
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=10,
        help="Number of endpoints to show (with -s)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🔄 Swagger Cache Refresh Tool")
    print("="*70)
    
    # Show current configuration
    base_urls = config.erp_api_base_urls()
    print(f"\nConfigured API URLs:")
    for url in base_urls:
        print(f"  • {url}")
    
    cache_path = config.swagger_json_path()
    print(f"\nCache location: {cache_path}")
    
    # Refresh the cache
    success = refresh_swagger_cache()
    
    if not success:
        print("\n❌ Failed to refresh cache")
        return 1
    
    # Show sample endpoints if requested
    if args.show:
        print(f"\n📋 Sample endpoints (showing {args.count}):")
        print("-" * 70)
        
        endpoints = load_swagger_generated_endpoints()
        for i, endpoint in enumerate(endpoints[:args.count], 1):
            path = endpoint.get("url", "?")
            desc = endpoint.get("description", "No description")
            required = endpoint.get("requiredParameters", [])
            
            print(f"\n{i}. {path}")
            print(f"   {desc}")
            
            if required:
                print(f"   📌 Required: {', '.join(required)}")
            
            if args.verbose:
                optional = endpoint.get("queryParameters", [])
                if optional:
                    print(f"   ℹ️  Optional: {', '.join(optional)}")
        
        if len(endpoints) > args.count:
            print(f"\n... and {len(endpoints) - args.count} more endpoints")
    
    print("\n" + "="*70)
    print("✅ Done!")
    print("="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
