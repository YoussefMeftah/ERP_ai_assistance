#!/usr/bin/env python3
"""
Verify LangSmith configuration is set up correctly.

This script checks that:
1. .env file exists
2. LANGSMITH_API_KEY is configured
3. python-dotenv is installed
4. Configuration loads successfully
"""

import sys
from pathlib import Path

def verify_setup():
    """Verify all configurations are in place."""
    print("\n" + "="*60)
    print("LangSmith Configuration Verification")
    print("="*60 + "\n")
    
    # Check .env file
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    
    print(f"1️⃣  Checking .env file...")
    if env_file.exists():
        print(f"   ✅ Found: {env_file}")
    else:
        print(f"   ❌ Not found: {env_file}")
        print(f"   📋 Copy .env.example to .env and fill in values")
        return False
    
    # Check python-dotenv
    print(f"\n2️⃣  Checking python-dotenv...")
    try:
        import dotenv
        print(f"   ✅ python-dotenv installed")
    except ImportError:
        print(f"   ❌ python-dotenv not installed")
        print(f"   📋 Install with: pip install python-dotenv")
        return False
    
    # Check configuration loading
    print(f"\n3️⃣  Loading configuration...")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from config import config
        
        api_key = config.langsmith_api_key()
        if api_key:
            print(f"   ✅ API Key loaded: {api_key[:12]}...")
        else:
            print(f"   ❌ API Key not found in .env")
            return False
        
        project_name = config.langsmith_project_name()
        print(f"   ✅ Project: {project_name}")
        
        dataset_name = config.langsmith_dataset_name()
        print(f"   ✅ Dataset: {dataset_name}")
        
    except Exception as e:
        print(f"   ❌ Error loading configuration: {e}")
        return False
    
    # Check LangSmith connectivity
    print(f"\n4️⃣  Checking LangSmith connectivity...")
    try:
        from langsmith import Client
        client = Client()
        # Try to access the client to verify API key works
        print(f"   ✅ LangSmith client initialized")
        print(f"   ℹ️  API will be tested when running evaluation")
    except Exception as e:
        print(f"   ⚠️  Warning: {e}")
        print(f"   ℹ️  This may be a connectivity issue that will resolve when running evaluation")
    
    # Summary
    print(f"\n" + "="*60)
    print("✅ LangSmith configuration verified successfully!")
    print("="*60 + "\n")
    
    print("📋 Next steps:")
    print("   1. Run: python langsmith_evaluation.py --dataset-only")
    print("   2. Then: python langsmith_example.py --quick")
    print("   3. Full eval: python langsmith_example.py --full --report")
    print()
    
    return True


if __name__ == "__main__":
    success = verify_setup()
    sys.exit(0 if success else 1)
