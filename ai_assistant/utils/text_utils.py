"""
Text processing utilities: tokenization, domain inference, parameter extraction.
"""

import re
from typing import List, Dict, Any, Set
from datetime import UTC, datetime


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words.
    
    Args:
        text: Input text
    
    Returns:
        List of lowercase alphanumeric tokens
    """
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def contains_any(text: str, terms: List[str]) -> bool:
    """Check if any term appears in text (case-insensitive).
    
    Args:
        text: Text to search
        terms: List of terms to look for
    
    Returns:
        True if any term found in text
    """
    lowered = text.lower()
    return any(term in lowered for term in terms)


def split_path_tokens(text: str) -> List[str]:
    """Split path-like strings into tokens, handling CamelCase.
    
    Examples:
        "/api/GetClients" -> ["api", "get", "clients"]
    
    Args:
        text: Input path or identifier
    
    Returns:
        List of lowercase tokens
    """
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    raw = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return [t for t in raw if t]


def singularize(token: str) -> str:
    """Simple singularization of English words.
    
    Args:
        token: Word to singularize
    
    Returns:
        Singularized form
    """
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def infer_domain_from_question(question: str) -> str:
    """Infer business domain from user question.
    
    Returns one of: "commercial", "stock", "finance", "rh", "achat", "general"
    
    Args:
        question: User's natural language question
    
    Returns:
        Domain identifier
    """
    q = question.lower()
    
    # Priority anchors for common ambiguous phrases
    if any(w in q for w in ["paiement", "paiements", "depense", "dépense", "transfert", "solde", "créance", "creance"]):
        return "finance"
    if any(w in q for w in ["fournisseur", "fournisseurs", "achat"]):
        return "achat"
    if any(w in q for w in ["employe", "employés", "paie", "congé", "conge", "salaire"]):
        return "rh"
    if any(w in q for w in ["stock", "inventaire", "depot", "dépôt", "lot"]):
        return "stock"
    
    # Keyword domain mapping
    domain_keywords = {
        "commercial": ["client", "clients", "commande", "commandes", "vente", "facture", "bl"],
        "stock": ["stock", "inventaire", "depot", "dépôt", "article", "articles", "lot"],
        "finance": ["paiement", "paiements", "depense", "dépense", "transfert", "solde", "creance", "créance"],
        "rh": ["employe", "employés", "paie", "conge", "congé", "salaire"],
        "achat": ["fournisseur", "fournisseurs", "achat", "frs"],
    }
    
    best_domain = "general"
    best_score = 0
    for domain, words in domain_keywords.items():
        score = sum(1 for w in words if w in q)
        if score > best_score:
            best_score = score
            best_domain = domain
    
    return best_domain


def infer_domain_from_path(path: str) -> str:
    """Infer business domain from API path.
    
    Args:
        path: API endpoint path
    
    Returns:
        Domain identifier
    """
    tokens = set(singularize(t) for t in split_path_tokens(path))
    
    if tokens.intersection({"client", "clients", "commande", "commandes", "blclient", "statsvente", "fact"}):
        return "commercial"
    if tokens.intersection({"stock", "depot", "lot", "article", "articles", "bonentree", "bontransfert"}):
        return "stock"
    if tokens.intersection({"paiement", "paiements", "depense", "depenses", "finance", "transfert"}):
        return "finance"
    if tokens.intersection({"demandeconge", "conge", "paie", "employe", "employes"}):
        return "rh"
    if tokens.intersection({"fournisseur", "fournisseurs", "blfrs", "frs"}):
        return "achat"
    
    return "general"


def extract_simple_params(question: str, add_defaults: bool = True) -> Dict[str, Any]:
    """Extract basic parameters from user question.
    
    Extracts: IDs, dates (various formats, year ranges)
    Optionally sets defaults for: DateDebut, DateFin, commercialCategory
    
    Year range examples:
        - "dans 2025" → "01-01-2025" to "12-31-2025"
        - "in 2024 and 2025" → "01-01-2024" to "12-31-2025"
        - "2024, 2025, 2026" → "01-01-2024" to "12-31-2026"
    
    Args:
        question: User question text
        add_defaults: Whether to add default DateDebut, DateFin, commercialCategory
    
    Returns:
        Dict of parameter names to values
    """
    out: Dict[str, Any] = {}
    
    # Extract numeric IDs
    id_match = re.search(
        r"\b(?:id|client|commande|article|employe)\s*(\d+)\b",
        question,
        re.IGNORECASE
    )
    if id_match:
        out["id"] = int(id_match.group(1))
    
    # First, try to extract year ranges (like "2024 and 2025" or just "2025")
    year_pattern = r"\b(20\d{2})\b"
    year_matches = re.findall(year_pattern, question)
    
    if year_matches:
        # Convert to integers and sort
        years = sorted(set(int(y) for y in year_matches))
        
        if years:
            # Use first year as start, last year as end
            start_year = years[0]
            end_year = years[-1]
            
            out["DateDebut"] = f"01-01-{start_year}"
            out["DateFin"] = f"12-31-{end_year}"
    else:
        # No years found, try to extract explicit dates in various formats
        date_patterns = [
            r"\b(20\d{2}-\d{2}-\d{2})\b",  # 2025-01-01
            r"\b(\d{2}-\d{2}-20\d{2})\b",  # 01-01-2025 or MM-DD-YYYY
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, question)
            dates_found.extend(matches)
        
        if dates_found:
            converted_dates = []
            for date_str in dates_found:
                try:
                    # Try parsing as YYYY-MM-DD first
                    if date_str.startswith("20"):
                        d = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        # Assume MM-DD-YYYY or DD-MM-YYYY
                        try:
                            d = datetime.strptime(date_str, "%m-%d-%Y")
                        except ValueError:
                            d = datetime.strptime(date_str, "%d-%m-%Y")
                    converted_dates.append(d.strftime("%m-%d-%Y"))
                except ValueError:
                    converted_dates.append(date_str)
            
            if len(converted_dates) >= 1:
                out["DateDebut"] = converted_dates[0]
            if len(converted_dates) >= 2:
                out["DateFin"] = converted_dates[1]
            elif len(converted_dates) == 1:
                out["DateFin"] = converted_dates[0]
    
    # Set default dates if not provided (and add_defaults=True)
    if add_defaults:
        if "DateDebut" not in out or "DateFin" not in out:
            today = datetime.now(UTC)
            year_start = today.replace(month=1, day=1)
            year_end = today.replace(month=12, day=31)
            
            if "DateDebut" not in out:
                out["DateDebut"] = year_start.strftime("%m-%d-%Y")
            if "DateFin" not in out:
                out["DateFin"] = year_end.strftime("%m-%d-%Y")
        
        # Default commercial category
        if "commercialCategory" not in out:
            out["commercialCategory"] = 1
    
    # Extract IsFrs (supplier vs customer indicator)
    q_lower = question.lower()
    # Check for supplier-specific keywords
    supplier_keywords = ["fournisseur", "supplier", "vendor", "achat", "purchase"]
    customer_keywords = ["client", "customer", "vente", "sale", "payment", "paiement"]
    
    # Default to False (customer-focused query) unless supplier keywords are present
    if "IsFrs" not in out:
        if any(word in q_lower for word in supplier_keywords):
            out["IsFrs"] = True
        else:
            out["IsFrs"] = False
    
    return out


def extract_params_for_endpoint(
    question: str,
    endpoint: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract parameters from question based on endpoint's expected parameters.
    
    Enhanced version of extract_simple_params that understands endpoint-specific
    parameter names and types.
    
    Args:
        question: User question text
        endpoint: Endpoint dict with parameterMetadata containing required/optional params
    
    Returns:
        Dict of parameter names to extracted values
    """
    out: Dict[str, Any] = {}
    q = question.lower()
    
    # Get endpoint's parameter metadata
    param_metadata = endpoint.get("parameterMetadata", {})
    required_params = param_metadata.get("required", [])
    optional_params = param_metadata.get("optional", [])
    detailed_params = param_metadata.get("detailed", {})
    
    all_param_names = required_params + optional_params
    
    # Process each expected parameter
    for param_name in all_param_names:
        param_detail = detailed_params.get(param_name, {})
        param_type = param_detail.get("type", "string").lower()
        
        extracted_value = None
        
        # Handle date parameters
        if param_type in ["date", "datetime"] or "date" in param_name.lower():
            # Check for year ranges first
            year_pattern = r"\b(20\d{2})\b"
            year_matches = re.findall(year_pattern, question)
            
            if year_matches:
                years = sorted(set(int(y) for y in year_matches))
                if years:
                    if "debut" in param_name.lower() or "start" in param_name.lower():
                        extracted_value = f"01-01-{years[0]}"
                    elif "fin" in param_name.lower() or "end" in param_name.lower():
                        extracted_value = f"12-31-{years[-1]}"
            
            # If no year found, try explicit dates
            if not extracted_value:
                date_patterns = [
                    r"\b(20\d{2}-\d{2}-\d{2})\b",
                    r"\b(\d{2}-\d{2}-20\d{2})\b",
                ]
                for pattern in date_patterns:
                    matches = re.findall(pattern, question)
                    if matches:
                        try:
                            if matches[0].startswith("20"):
                                d = datetime.strptime(matches[0], "%Y-%m-%d")
                            else:
                                try:
                                    d = datetime.strptime(matches[0], "%m-%d-%Y")
                                except ValueError:
                                    d = datetime.strptime(matches[0], "%d-%m-%Y")
                            extracted_value = d.strftime("%m-%d-%Y")
                            break
                        except ValueError:
                            extracted_value = matches[0]
                            break
            
            # Default date: current year
            if not extracted_value:
                today = datetime.now(UTC)
                if "debut" in param_name.lower() or "start" in param_name.lower():
                    extracted_value = today.replace(month=1, day=1).strftime("%m-%d-%Y")
                elif "fin" in param_name.lower() or "end" in param_name.lower():
                    extracted_value = today.replace(month=12, day=31).strftime("%m-%d-%Y")
        
        # Handle numeric/ID parameters
        elif param_type in ["integer", "number", "int", "double", "float"]:
            # Look for pattern like "param_name number"
            id_patterns = [
                rf"\b{param_name}\s*(\d+)\b",
                rf"\b({param_name.split('_')[0]})\s*(\d+)\b",  # Try first part of camelCase
                r"\b(?:id|number|num|code|client|product|article)\s*(\d+)\b",
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, q, re.IGNORECASE)
                if match:
                    extracted_value = int(match.group(1) if match.lastindex == 1 else match.group(2))
                    break
        
        # Handle string parameters
        elif param_type == "string":
            # Look for quoted strings or specific keywords
            quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', question)
            if quoted:
                extracted_value = quoted[0][0] or quoted[0][1]
            
            # Or look for common keywords in question
            if not extracted_value:
                keywords = ["category", "type", "name", "status", "code"]
                for kw in keywords:
                    if kw in param_name.lower():
                        # Try to find a relevant value
                        pattern = rf"\b{kw}\s+(\w+)\b"
                        match = re.search(pattern, q, re.IGNORECASE)
                        if match:
                            extracted_value = match.group(1)
                            break
        
        # Add extracted value if found
        if extracted_value is not None:
            out[param_name] = extracted_value
            print(f"[DEBUG] Endpoint-aware extraction: {param_name} = {extracted_value}")
    
    return out
