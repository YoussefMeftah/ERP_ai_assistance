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


def extract_simple_params(question: str) -> Dict[str, Any]:
    """Extract basic parameters from user question.
    
    Extracts: IDs, dates (various formats, year ranges)
    Sets defaults for: DateDebut, DateFin, commercialCategory
    
    Year range examples:
        - "dans 2025" → "01-01-2025" to "12-31-2025"
        - "in 2024 and 2025" → "01-01-2024" to "12-31-2025"
        - "2024, 2025, 2026" → "01-01-2024" to "12-31-2026"
    
    Args:
        question: User question text
    
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
    
    # Set default dates if not provided
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
    
    return out
