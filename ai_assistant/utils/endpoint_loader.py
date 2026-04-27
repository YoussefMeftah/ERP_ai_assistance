"""
Endpoint loading from multiple sources: Swagger, JSON configuration, and overrides.
"""

import re
import json
import requests
import urllib3
from pathlib import Path
from typing import Dict, List, Any, Optional
from config import config
from .text_utils import split_path_tokens, singularize, contains_any

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def path_to_generated_id(path: str, method: str) -> str:
    """Generate a canonical endpoint ID from path and method.
    
    Examples:
        ("/api/Clients/GetAll", "GET") -> "webapi_get_api_clients_getall"
    
    Args:
        path: API endpoint path
        method: HTTP method
    
    Returns:
        Generated endpoint ID
    """
    tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", path.lower()) if t]
    return "webapi_" + method.lower() + "_" + "_".join(tokens)


def path_to_keywords(path: str) -> List[str]:
    """Extract keywords from endpoint path for semantic matching.
    
    Args:
        path: API path or description
    
    Returns:
        List of relevant keywords (max 8), excluding stop words
    """
    expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", path)
    tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", expanded.lower()) if t]
    
    stop_words = {"api", "odata", "get", "all", "by", "id", "v1", "swagger"}
    uniq: List[str] = []
    for t in tokens:
        if t in stop_words:
            continue
        if t not in uniq:
            uniq.append(t)
    
    return uniq[:8]


def _cache_swagger_to_file(payload: Dict[str, Any]) -> None:
    """Cache Swagger spec to file for offline fallback.
    
    Args:
        payload: Swagger spec dict to cache
    """
    try:
        cache_path = config.swagger_json_path()
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"[INFO] ✅ Cached Swagger spec to {cache_path}")
    except Exception as e:
        print(f"[WARNING] Failed to cache Swagger spec: {e}")


def load_swagger_payload() -> Dict[str, Any]:
    """Load Swagger specification from live API or fallback file.
    
    Priority:
        1. Live API: GET {ERP_API_BASE_URL}/swagger/v1/swagger.json (auto-caches to file)
        2. Fallback file: ERP_SWAGGER_JSON env var
        3. Fallback file: {AI_ASSISTANT_ROOT}/swagger_live.json
    
    Returns:
        Swagger spec dict (or empty dict if not found)
    """
    base_urls = config.erp_api_base_urls()
    for base_url in base_urls:
        try:
            print(f"[INFO] 🔄 Fetching Swagger from {base_url}/swagger/v1/swagger.json...")
            response = requests.get(
                f"{base_url}/swagger/v1/swagger.json",
                timeout=20,
                verify=False
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                # Auto-cache the fetched spec
                _cache_swagger_to_file(payload)
                print(f"[INFO] ✅ Loaded Swagger from live API ({len(payload.get('paths', {}))} paths)")
                return payload
        except requests.RequestException as e:
            print(f"[WARNING] Failed to fetch Swagger from {base_url}: {e}")
            continue
    
    # Fallback to file
    print(f"[INFO] ⏸️  Live API unavailable, using cached Swagger spec...")
    fallback_path = config.swagger_json_path()
    if fallback_path and fallback_path.exists():
        try:
            payload = json.loads(fallback_path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                print(f"[INFO] ✅ Loaded cached Swagger from {fallback_path} ({len(payload.get('paths', {}))} paths)")
                return payload
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARNING] Failed to load cached Swagger: {e}")
            pass
    
    print(f"[WARNING] ⚠️  No Swagger spec available (live API down, no cache)")
    return {}


def extract_parameter_metadata(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract rich parameter metadata from Swagger parameters.
    
    Captures type, required flag, description, and examples for each parameter.
    
    Args:
        parameters: List of parameter dicts from Swagger operation
    
    Returns:
        Dict with 'required', 'optional', and 'detailed' parameter info
    """
    param_info = {
        "required": [],       # List of required param names
        "optional": [],       # List of optional param names
        "detailed": {}        # Dict mapping param name to full metadata
    }
    
    if not isinstance(parameters, list):
        return param_info
    
    for param in parameters:
        if not isinstance(param, dict):
            continue
        
        name = param.get("name")
        if not name:
            continue
        
        # Extract parameter details
        param_type = "string"
        schema = param.get("schema", {})
        if isinstance(schema, dict):
            param_type = schema.get("type", "string")
        
        is_required = param.get("required", False)
        description = param.get("description", "")
        param_in = param.get("in", "query")
        
        # Build detailed metadata
        metadata = {
            "name": name,
            "type": param_type,
            "in": param_in,
            "required": is_required,
            "description": description,
        }
        
        # Add example if available
        if "example" in schema:
            metadata["example"] = schema["example"]
        elif "default" in schema:
            metadata["default"] = schema["default"]
        
        param_info["detailed"][name] = metadata
        
        # Categorize as required or optional
        if is_required or param_in == "path":
            param_info["required"].append(name)
        else:
            param_info["optional"].append(name)
    
    return param_info


def load_swagger_generated_endpoints() -> List[Dict[str, Any]]:
    """Generate endpoint definitions from Swagger specification.
    
    Returns:
        List of endpoint dicts with full metadata including parameter details
    """
    generated: List[Dict[str, Any]] = []
    swagger_payload = load_swagger_payload()
    swagger_paths = swagger_payload.get("paths", {})
    
    if not isinstance(swagger_paths, dict) or not swagger_paths:
        return generated
    
    for path, methods in swagger_paths.items():
        if not isinstance(methods, dict):
            continue
        
        for method_name, operation in methods.items():
            method = str(method_name).upper()
            if method != "GET":
                continue
            
            operation = operation if isinstance(operation, dict) else {}
            tags = [str(tag) for tag in operation.get("tags", []) if tag]
            summary = str(operation.get("summary", ""))
            description = str(operation.get("description", ""))
            operation_id = str(operation.get("operationId", ""))
            parameters = operation.get("parameters", [])
            
            # Extract rich parameter metadata
            param_metadata = extract_parameter_metadata(parameters)
            
            query_parameters = [
                str(param.get("name"))
                for param in parameters
                if isinstance(param, dict) and param.get("in") == "query" and param.get("name")
            ]
            route_parameters = [
                str(param.get("name"))
                for param in parameters
                if isinstance(param, dict) and param.get("in") == "path" and param.get("name")
            ]
            
            # Generate keywords from path, summary, description, etc.
            keyword_text = " ".join([
                path, summary, description, operation_id,
                " ".join(tags), " ".join(query_parameters)
            ])
            keywords = path_to_keywords(keyword_text)
            
            # Infer domain from path/description
            from .text_utils import infer_domain_from_path as infer_domain
            role = infer_domain(path)
            
            # Determine if this is a statistical/aggregation endpoint
            is_stats = contains_any(
                path + " " + summary + " " + description,
                ["stat", "report", "vente", "chiffre", "dashboard"]
            )
            
            generated.append({
                "id": path_to_generated_id(path, method),
                "method": method,
                "url": path,
                "intent": "AGGREGATE" if is_stats else "GET",
                "keywords": keywords,
                "routeParameters": route_parameters or re.findall(r"\{([^{}]+)\}", path),
                "queryParameters": query_parameters,
                "requiredParameters": route_parameters or re.findall(r"\{([^{}]+)\}", path),
                "responseFormat": "Object",
                "description": description or summary or f"Generated from Swagger: {path}",
                "examples": [],
                "role": role,
                "tags": tags,
                "parameterMetadata": param_metadata,
            })
    
    return generated


def load_endpoints() -> List[Dict[str, Any]]:
    """Load endpoint definitions from configured sources.
    
    Priority:
        1. Swagger (if ERP_ENDPOINT_SOURCE=swagger and ERP_LOAD_SWAGGER_ENDPOINTS=1)
        2. JSON file (ERP_ENDPOINTS_JSON or data/endpoints.sample.json)
    
    Returns:
        List of endpoint definitions
    """
    source_mode = config.endpoint_source()
    
    # Try Swagger if enabled
    if source_mode == "swagger" and config.load_swagger_endpoints():
        swagger_endpoints = load_swagger_generated_endpoints()
        if swagger_endpoints:
            return swagger_endpoints
    
    # Fallback to JSON file
    endpoints_path = config.endpoints_json_path()
    if not endpoints_path or not endpoints_path.exists():
        return []
    
    try:
        payload = json.loads(endpoints_path.read_text(encoding="utf-8"))
        configured_endpoints = payload.get("endpoints", [])
        return configured_endpoints
    except (json.JSONDecodeError, OSError):
        return []


def load_endpoint_overrides() -> Dict[str, str]:
    """Load endpoint ID -> URL mapping overrides.
    
    Allows safe correction of endpoint URLs without modifying source files.
    
    Returns:
        Dict mapping endpoint IDs to corrected URLs
    """
    overrides_path = config.endpoint_overrides_path()
    if not overrides_path or not overrides_path.exists():
        return {}
    
    try:
        payload = json.loads(overrides_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
    except (json.JSONDecodeError, OSError):
        pass
    
    return {}


def refresh_swagger_cache() -> bool:
    """Manually refresh the Swagger cache from live API.
    
    Useful for forcing an update of the cached Swagger spec.
    
    Returns:
        True if cache was updated, False otherwise
    """
    print("\n[INFO] 🔄 Refreshing Swagger cache from live API...")
    base_urls = config.erp_api_base_urls()
    
    for base_url in base_urls:
        try:
            print(f"[INFO] Trying {base_url}/swagger/v1/swagger.json...")
            response = requests.get(
                f"{base_url}/swagger/v1/swagger.json",
                timeout=20,
                verify=False
            )
            response.raise_for_status()
            payload = response.json()
            
            if isinstance(payload, dict) and payload.get("paths"):
                _cache_swagger_to_file(payload)
                endpoint_count = len(payload.get("paths", {}))
                print(f"[INFO] ✅ Swagger cache updated! Found {endpoint_count} endpoints")
                return True
        except requests.RequestException as e:
            print(f"[WARNING] Failed: {e}")
            continue
    
    print(f"[ERROR] ❌ Could not refresh cache - all APIs unavailable")
    return False
