"""Scoring logic for endpoint candidate retrieval."""

from typing import List, Dict, Any
from utils.text_utils import tokenize, contains_any


def is_supported_business_endpoint(endpoint: Dict[str, Any]) -> bool:
    """Check if endpoint is a business endpoint (not test/auth/debug).
    
    Args:
        endpoint: Endpoint definition
    
    Returns:
        True if endpoint is suitable for business queries
    """
    if str(endpoint.get("method", "GET")).upper() != "GET":
        return False
    
    url = str(endpoint.get("url", "")).lower()
    endpoint_id = str(endpoint.get("id", "")).lower()
    description = str(endpoint.get("description", "")).lower()
    tags = " ".join(str(tag) for tag in endpoint.get("tags", [])).lower()
    endpoint_text = " ".join([url, endpoint_id, description, tags])
    
    # Block test/debug endpoints
    blocked_terms = [
        "swagger", "openapi", "health", "generate-test", "generatetest",
        "/test", "testendpoint", "debug", "token", "login", "signin", "auth"
    ]
    if contains_any(endpoint_text, blocked_terms):
        return False
    
    # Report endpoints must contain business keywords
    if "/api/reports/" in url:
        business_keywords = ["vente", "commande", "client", "fact", "report"]
        if not contains_any(endpoint_text, business_keywords):
            return False
    
    # Must contain business keywords
    business_allow_terms = [
        "getall", "list", "all", "odata", "client", "commande",
        "vente", "stock", "paiement", "fournisseur", "fact",
        "article", "report", "stats"
    ]
    return contains_any(endpoint_text, business_allow_terms)


def compute_endpoint_score(
    endpoint: Dict[str, Any],
    q_tokens: set,
    question: str,
    intent: str,
    domain: str,
) -> int:
    """Compute relevance score for an endpoint given question.
    
    Scoring factors:
        - Token overlap with question (base score)
        - Intent match (GET vs AGGREGATE)
        - Domain role match (commercial, stock, etc.)
        - URL patterns (getall, list, odata bonus)
        - Keyword-specific bonuses (achat > vente for purchase questions, etc.)
        - Special handling for specific endpoints
    
    Args:
        endpoint: Endpoint definition
        q_tokens: Tokens from question
        question: Original question
        intent: Classified intent
        domain: Classified domain
    
    Returns:
        Relevance score
    """
    ep_keywords = [str(kw).lower() for kw in endpoint.get("keywords", [])]
    ep_text = " ".join([
        str(endpoint.get("id", "")),
        str(endpoint.get("url", "")),
        str(endpoint.get("description", "")),
        " ".join(ep_keywords),
        " ".join(str(tag) for tag in endpoint.get("tags", [])),
    ]).lower()
    ep_tokens = set(tokenize(ep_text))
    
    # Base score: token overlap
    overlap = len(q_tokens.intersection(ep_tokens))
    role_match = endpoint.get("role") == domain
    intent_match = endpoint.get("intent") == intent
    
    score = overlap * 4
    url = str(endpoint.get("url", "")).lower()
    
    # Intent and role bonuses
    if overlap > 0 and intent_match:
        score += 2
    if overlap > 0 and role_match:
        score += 1
    
    # URL pattern bonuses
    if contains_any(ep_text, ["getall", "list", "odata"]):
        score += 4
    if contains_any(url, ["/api/reports/commande_client-report", "/api/statsvente/"]):
        score += 5
    
    # Penalty for debug/test
    if contains_any(ep_text, ["generate-test", "generatetest", "/test", "debug"]):
        score -= 20
    
    # Keyword-specific matching bonuses (high priority for StatsAchats, StatsPaiements)
    if contains_any(question, ["achat", "achats"]):
        if contains_any(ep_text, ["achat", "achats", "statsachats"]):
            score += 10  # Strong bonus for purchase questions
        elif contains_any(ep_text, ["vente", "ventes", "statsvente"]):
            score -= 5  # Penalty if StatsVente selected instead of StatsAchats
    
    if contains_any(question, ["paiement", "paiements", "reglement", "règlement", "versement"]):
        if contains_any(ep_text, ["paiement", "paiements", "statspaiements", "payment", "payments"]):
            score += 10  # Strong bonus for payment questions
        elif contains_any(ep_text, ["vente", "ventes", "statsvente"]):
            score -= 5  # Penalty if StatsVente selected instead of StatsPaiements
    
    # Sales/statistics specific
    if contains_any(question, ["vente", "ventes", "statistique", "statistiques", "chiffre", "ca", "rapport"]):
        # Only apply vente bonus if NOT achat/paiement
        if not contains_any(question, ["achat", "achats", "paiement", "paiements"]):
            if contains_any(ep_text, ["vente", "ventes", "statsvente", "report", "reports", "commande_client", "fact"]):
                score += 6
        if contains_any(ep_text, ["client/getallclients", "get_clients", "blclient/getallclients"]):
            score -= 4
    
    # Domain-specific bonuses
    if contains_any(question, ["client", "clients"]) and contains_any(ep_text, ["client", "clients"]):
        score += 3
    if contains_any(question, ["stock", "inventaire"]) and contains_any(ep_text, ["stock", "depot", "article"]):
        score += 5
    
    return score


def score_endpoints(
    endpoints: List[Dict[str, Any]],
    question: str,
    intent: str,
    domain: str,
    apply_business_filter: bool = True,
    apply_domain_filter: bool = True,
) -> List[Dict[str, Any]]:
    """Score and rank endpoints by relevance to question.
    
    Args:
        endpoints: List of available endpoints
        question: User question
        intent: Classified intent
        domain: Classified domain
        apply_business_filter: Whether to filter out non-business endpoints
        apply_domain_filter: Whether to apply strict domain matching (for test endpoints, set False)
    
    Returns:
        Sorted list of endpoints with scores (highest first)
    """
    q_tokens = set(tokenize(question))
    scored: List[Dict[str, Any]] = []
    all_endpoints_with_scores: List[Dict[str, Any]] = []
    
    for ep in endpoints:
        # Apply business filter if requested
        if apply_business_filter and not is_supported_business_endpoint(ep):
            continue
        
        # Filter by domain for Swagger-generated endpoints (can be disabled for test endpoints)
        if apply_domain_filter and str(ep.get("id", "")).startswith("webapi_get_"):
            role = ep.get("role", "general")
            if domain != "general" and role not in {domain, "general"}:
                continue
        
        score = compute_endpoint_score(
            endpoint=ep,
            q_tokens=q_tokens,
            question=question,
            intent=intent,
            domain=domain,
        )
        
        all_endpoints_with_scores.append({"score": score, **ep})
        if score > 0:
            scored.append({"score": score, **ep})
    
    # Fallback: if no endpoints scored > 0, return all with their scores
    if not scored and all_endpoints_with_scores:
        scored = all_endpoints_with_scores
    
    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
