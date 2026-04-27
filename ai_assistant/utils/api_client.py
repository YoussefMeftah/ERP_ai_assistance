"""
API client for calling Ollama and other external services.
"""

import json
import requests
import urllib3
from typing import Any, Dict, Optional
from config import config

# Suppress SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def call_ollama_chat(
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: Optional[int] = None,
) -> str:
    """Call Ollama chat API with system and user prompts.
    
    Args:
        model: Model name (e.g., "llama3.1:8b", "deepseek-coder:6.7b")
        system_prompt: System message to guide the model
        user_prompt: User message/question
        timeout_seconds: Request timeout (defaults to OLLAMA_TIMEOUT_SECONDS)
    
    Returns:
        Model's text response (stripped)
    
    Raises:
        requests.RequestException: On HTTP/network errors
        ValueError: If response format is invalid
    """
    if timeout_seconds is None:
        timeout_seconds = config.ollama_timeout_seconds()
    
    url = config.ollama_url()
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    
    response = requests.post(url, json=payload, timeout=timeout_seconds, verify=False)
    response.raise_for_status()
    
    content = response.json().get("message", {}).get("content", "")
    return content.strip()


def call_ollama_json(
    model: str,
    system_prompt: str,
    user_prompt: str,
    debug: bool = False,
) -> Optional[Dict[str, Any]]:
    """Call Ollama and expect JSON response.
    
    Automatically handles JSON extraction from wrapped responses (```json...```).
    
    Args:
        model: Model name
        system_prompt: System message
        user_prompt: User message
        debug: If True, print raw response for debugging
    
    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    router_timeout = config.ollama_router_timeout_seconds()
    raw = call_ollama_chat(model, system_prompt, user_prompt, timeout_seconds=router_timeout)
    
    if debug:
        print(f"[DEBUG] Raw response from {model}:")
        print(f"  Length: {len(raw)} chars")
        print(f"  First 200 chars: {raw[:200]!r}")
        print(f"  Full response: {raw!r}")
    
    # Clean markdown fence wrappers
    cleaned = raw.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as e:
        if debug:
            print(f"[DEBUG] JSON parse error: {e}")
            print(f"[DEBUG] Cleaned text: {cleaned!r}")
        return None
    
    return None
