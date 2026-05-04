"""Utility modules for the ERP AI Assistant."""

from .api_client import (
    call_ollama_chat,
    call_ollama_json,
)
from .text_utils import (
    tokenize,
    infer_domain_from_question,
    infer_domain_from_path,
    extract_simple_params,
    extract_params_for_endpoint,
    contains_any,
)
from .endpoint_loader import (
    load_endpoints,
    load_endpoint_overrides,
    load_swagger_payload,
)
from .data_processing import (
    normalize_data_field,
    build_answer_evidence,
    truncate_text,
)

__all__ = [
    "call_ollama_chat",
    "call_ollama_json",
    "tokenize",
    "infer_domain_from_question",
    "infer_domain_from_path",
    "extract_simple_params",
    "extract_params_for_endpoint",
    "contains_any",
    "load_endpoints",
    "load_endpoint_overrides",
    "load_swagger_payload",
    "normalize_data_field",
    "build_answer_evidence",
    "truncate_text",
]
