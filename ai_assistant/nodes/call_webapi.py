"""Node: Execute API calls to the ERP WebAPI."""

import re
import json
import requests
import urllib3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import UTC, datetime
from urllib.parse import urlencode

from state import AssistantState
from config import config
from utils.data_processing import normalize_data_field
from utils.endpoint_loader import load_endpoint_overrides

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def build_endpoint_url(url_template: str, params: Dict[str, Any]) -> str:
    """Render endpoint URL by substituting route parameters.
    
    Args:
        url_template: Template like "/api/Client/{id}"
        params: Parameter dict
    
    Returns:
        Rendered URL with parameters substituted
    """
    route_params = re.findall(r"\{([^{}]+)\}", url_template)
    rendered = url_template
    
    for route_key in route_params:
        value = params.get(route_key)
        if value is None:
            # Try smart fallback
            if route_key.lower() == "code" and "id" in params:
                value = params.get("id")
            elif route_key.lower() == "id" and "code" in params:
                value = params.get("code")
        
        if value is not None:
            rendered = rendered.replace(f"{{{route_key}}}", str(value))
    
    return rendered


def collect_request_parts(
    selected: Dict[str, Any],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Collect query parameters and check for missing required parameters.
    
    Args:
        selected: Selected endpoint definition
        params: Extracted parameters
    
    Returns:
        Dict with missing_required and query_params
    """
    required = selected.get("requiredParameters", [])
    query_keys = selected.get("queryParameters", [])
    
    missing_required = [key for key in required if key not in params]
    query_params = {k: params[k] for k in query_keys if k in params}
    
    # Safe defaults for pagination
    if "pageNumber" in query_keys and "pageNumber" not in query_params:
        query_params["pageNumber"] = 1
    if "pageSize" in query_keys and "pageSize" not in query_params:
        query_params["pageSize"] = 50
    
    # Special handling for StatsVente endpoints - add default date parameters
    endpoint_id = selected.get("id", "").lower()
    if "statsvente" in endpoint_id:
        current_year = datetime.now().year
        
        # Add DateDebut if required/absent
        if "DateDebut" in query_keys and "DateDebut" not in query_params:
            query_params["DateDebut"] = f"01-01-{current_year}"
        
        # Add DateFin if required/absent
        if "DateFin" in query_keys and "DateFin" not in query_params:
            query_params["DateFin"] = f"12-31-{current_year}"
        
        # Add commercialCategory = 1 always for StatsVente
        if "commercialCategory" in query_keys:
            query_params["commercialCategory"] = 1
    
    return {
        "missing_required": missing_required,
        "query_params": query_params,
    }


def fetch_swagger_paths_with_methods(base_urls: List[str]) -> Dict[str, List[str]]:
    """Fetch Swagger paths and their HTTP methods.
    
    Args:
        base_urls: List of ERP API base URLs
    
    Returns:
        Dict mapping paths to list of methods
    """
    for base_url in base_urls:
        try:
            response = requests.get(
                f"{base_url}/swagger/v1/swagger.json",
                timeout=20,
                verify=False
            )
            response.raise_for_status()
            payload = response.json()
            path_map: Dict[str, List[str]] = {}
            for path, methods in payload.get("paths", {}).items():
                if isinstance(methods, dict):
                    path_map[path] = [m.upper() for m in methods.keys()]
            if path_map:
                return path_map
        except requests.RequestException:
            continue
    return {}


def resolve_endpoint_path_from_swagger(
    requested_path: str,
    method: str,
    selected: Dict[str, Any],
    swagger_paths: Dict[str, List[str]],
) -> str:
    """Resolve endpoint path using Swagger spec (fuzzy matching for path variations).
    
    Args:
        requested_path: Requested endpoint path
        method: HTTP method
        selected: Selected endpoint dict
        swagger_paths: Swagger paths from API
    
    Returns:
        Best matching path from Swagger
    """
    from utils.text_utils import split_path_tokens, singularize
    
    if not swagger_paths:
        return requested_path
    
    method = method.upper()
    
    # Exact match
    if requested_path in swagger_paths and method in swagger_paths[requested_path]:
        return requested_path
    
    # Case-insensitive match
    for path, methods in swagger_paths.items():
        if path.lower() == requested_path.lower() and method in methods:
            return path
    
    # Fuzzy token matching
    req_tokens = set(singularize(t) for t in split_path_tokens(requested_path))
    req_tokens.update(singularize(t) for t in split_path_tokens(selected.get("id", "")))
    for kw in selected.get("keywords", []):
        req_tokens.update(singularize(t) for t in split_path_tokens(str(kw)))
    
    requires_identifier = bool(
        selected.get("requiredParameters") or selected.get("routeParameters")
    )
    core_tokens = {
        t for t in (singularize(x) for x in split_path_tokens(requested_path))
        if t not in {"api", "odata"}
    }
    requested_tail = requested_path.strip("/").split("/")[-1]
    requested_tail_norm = re.sub(r"[^a-zA-Z0-9]+", "", requested_tail.lower())
    
    best_path = requested_path
    best_score = -1
    
    for path, methods in swagger_paths.items():
        if method not in methods:
            continue
        
        path_tokens = set(singularize(t) for t in split_path_tokens(path))
        overlap = len(req_tokens.intersection(path_tokens))
        bonus = 0
        
        # Request/API prefix bonus
        if requested_path.lower().startswith("/api/") and path.lower().startswith("/api/"):
            bonus += 1
        
        # GET method bonuses
        if method == "GET" and any(tok in path_tokens for tok in ["get", "all", "list"]):
            bonus += 1
        
        # Identifier handling
        if not requires_identifier and any(tok in path_tokens for tok in ["all", "list"]):
            bonus += 2
        if not requires_identifier and ("byid" in path.lower() or "{" in path):
            bonus -= 3
        if requires_identifier and ("byid" in path.lower() or "{" in path):
            bonus += 1
        
        # Core tokens check
        core_overlap = len(core_tokens.intersection(path_tokens))
        if core_overlap == 0:
            bonus -= 3
        
        # Tail matching
        path_norm = re.sub(r"[^a-zA-Z0-9]+", "", path.lower())
        if requested_tail_norm and requested_tail_norm in path_norm:
            bonus += 3
        
        score = overlap + (2 * core_overlap) + bonus
        if score > best_score:
            best_score = score
            best_path = path
    
    return best_path


def call_webapi(state: AssistantState) -> AssistantState:
    """Execute HTTP calls to selected endpoints and cache results.
    
    Steps:
        1. Validate endpoint selection
        2. Build URLs with parameters
        3. Execute HTTP requests
        4. Normalize responses
        5. Cache to last_api_result.json
    
    Args:
        state: Current graph state
    
    Returns:
        Updated state with api_result_path
    """
    selected = state.get("selected_endpoint")
    selected_endpoints = state.get("selected_endpoints", [])
    params = state.get("extracted_params", {})
    errors = state.get("errors", []).copy()
    
    # Ensure we have endpoints to call
    if not selected_endpoints and selected:
        selected_endpoints = [selected]
    
    if not selected_endpoints:
        errors.append("Cannot execute WebApi: no endpoint selected.")
        payload = {
            "generatedAt": datetime.now(UTC).isoformat(),
            "endpoints": [],
            "params": params,
            "calls": [],
            "data": [],
        }
        path = config.CACHE_DIR / "last_api_result.json"
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return {"api_result_path": str(path), "errors": errors}
    
    # Get ERP API configuration
    base_urls = config.erp_api_base_urls()
    if not base_urls:
        errors.append("Missing ERP_API_BASE_URL environment variable.")
        payload = {
            "generatedAt": datetime.now(UTC).isoformat(),
            "endpoints": [ep.get("id") for ep in selected_endpoints],
            "params": params,
            "calls": [],
            "data": [],
        }
        path = config.CACHE_DIR / "last_api_result.json"
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return {"api_result_path": str(path), "errors": errors}
    
    # Load overrides and Swagger paths
    overrides = load_endpoint_overrides()
    swagger_paths = fetch_swagger_paths_with_methods(base_urls)
    
    # Prepare headers with Bearer token authentication
    headers: Dict[str, str] = {}
    bearer = config.erp_api_bearer_token()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    
    # Execute calls
    call_results: List[Dict[str, Any]] = []
    merged_data: List[Dict[str, Any]] = []
    
    for endpoint in selected_endpoints:
        endpoint_url = build_endpoint_url(endpoint.get("url", ""), params)
        override_path = overrides.get(str(endpoint.get("id", "")))
        if override_path:
            endpoint_url = build_endpoint_url(override_path, params)
        
        request_parts = collect_request_parts(endpoint, params)
        missing_required = request_parts["missing_required"]
        query_params = request_parts["query_params"]
        
        if missing_required:
            errors.append(
                f"Missing required parameters for {endpoint.get('id')}: {', '.join(missing_required)}"
            )
            call_results.append({
                "endpoint": endpoint.get("id"),
                "url": endpoint.get("url"),
                "resolvedUrl": endpoint_url,
                "fullUrl": None,
                "query": query_params,
                "statusCode": None,
                "dataCount": 0,
                "error": f"Missing: {', '.join(missing_required)}",
                "raw": None,
            })
            continue
        
        method = endpoint.get("method", "GET").upper()
        resolved_path = resolve_endpoint_path_from_swagger(
            requested_path=endpoint_url,
            method=method,
            selected=endpoint,
            swagger_paths=swagger_paths,
        )
        
        # Build candidate URLs
        candidate_urls: List[str] = []
        for base_url in base_urls:
            full_url = f"{base_url}{resolved_path}"
            if query_params:
                full_url = f"{full_url}?{urlencode(query_params, doseq=True)}"
            candidate_urls.append(full_url)
        
        # Try each URL
        last_exc: Optional[Exception] = None
        endpoint_payload: Dict[str, Any] = {
            "endpoint": endpoint.get("id"),
            "url": endpoint.get("url"),
            "resolvedUrl": resolved_path,
            "fullUrl": None,
            "query": query_params,
            "statusCode": None,
            "dataCount": 0,
            "error": None,
            "raw": None,
        }
        
        for full_url in candidate_urls:
            try:
                response = requests.get(
                    full_url,
                    headers=headers,
                    timeout=60,
                    verify=False
                )
                response.raise_for_status()
                
                # Parse response
                content_type = response.headers.get("Content-Type", "").lower()
                if "json" in content_type:
                    body = response.json()

                else:
                    raw_text = response.text.strip()
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"text": raw_text} if raw_text else {"text": ""}
                
                # Normalize to list of records
                data = normalize_data_field(body)
                
                # Update endpoint payload
                endpoint_payload = {
                    "endpoint": endpoint.get("id"),
                    "url": endpoint.get("url"),
                    "resolvedUrl": resolved_path,
                    "fullUrl": full_url,
                    "query": query_params,
                    "statusCode": response.status_code,
                    "dataCount": len(data),
                    "error": None,
                    "raw": body,
                }
                
                # Add records to merged data
                for record in data:
                    merged_data.append({
                        "endpoint": endpoint.get("id"),
                        "sourceUrl": full_url,
                        "record": record,
                    })
                
                last_exc = None
                break
            except requests.RequestException as exc:
                last_exc = exc
        
        if last_exc is not None:
            errors.append(f"WebApi call failed for {endpoint.get('id')}: {last_exc}")
            endpoint_payload["error"] = str(last_exc)
        
        call_results.append(endpoint_payload)
    
    # Cache results to file
    payload: Dict[str, Any] = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "endpoints": [ep.get("id") for ep in selected_endpoints],
        "params": params,
        "calls": call_results,
        "data": merged_data,
    }
    
    path = config.CACHE_DIR / "last_api_result.json"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    # Save to MongoDB for NoSQL querying
    collection_name = None
    data_headers = []
    if merged_data:
        # Generate collection name from endpoints
        endpoint_ids = [ep.get("id", "unknown") for ep in selected_endpoints]
        collection_name = "_".join(endpoint_ids)[:100]  # Limit collection name length
        
        # Extract data headers from first record
        if isinstance(merged_data, list) and len(merged_data) > 0:
            first_record = merged_data[0]
            if isinstance(first_record, dict):
                # Check if records have nested 'record' field with actual data
                if "record" in first_record and isinstance(first_record["record"], dict):
                    # Extract headers from nested record
                    data_headers = list(first_record["record"].keys())
                    print(f"[DEBUG] Extracted nested record headers: {data_headers}")
                else:
                    # Use top-level headers
                    data_headers = list(first_record.keys())
        
        # Debug: Show what's being saved to MongoDB
        print(f"\n[DEBUG] ===== MONGODB DATA SAVE =====")
        print(f"[DEBUG] Collection: {collection_name}")
        print(f"[DEBUG] Record count: {len(merged_data)}")
        print(f"[DEBUG] Data headers: {data_headers}")
        if len(merged_data) > 0:
            print(f"[DEBUG] First record sample: {json.dumps(merged_data[0], indent=2, default=str)[:500]}")
        print(f"[DEBUG] ================================\n")
        
        # Try to save to MongoDB
        try:
            from utils.mongodb_staging import connect_mongodb
            db = connect_mongodb()
            if db is not None:
                collection = db[collection_name]
                collection.drop()  # Clear old data
                collection.insert_many(merged_data)  # Insert new data
                print(f"[DEBUG] Successfully saved {len(merged_data)} records to MongoDB collection '{collection_name}'")
        except Exception as e:
            errors.append(f"Warning: Failed to save results to MongoDB: {e}")
            print(f"[DEBUG] MongoDB save failed: {e}")
    else:
        print(f"[DEBUG] No data to save to MongoDB (merged_data is empty)")
    
    return {
        "api_result_path": str(path),
        "collection_name": collection_name,
        "data_headers": data_headers,
        "errors": errors
    }
