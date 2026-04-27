"""Node: Use Llama to generate MongoDB NoSQL queries from user questions."""



import json

from typing import Dict, Any, List, Optional

from state import AssistantState

from config import config

from utils.api_client import call_ollama_json


def _is_simple_count_query(question: str) -> bool:
    """Detect if question is asking for simple total count (no unique/different).
    
    Returns True if question contains count keywords but NOT unique/distinct keywords.
    This allows us to bypass Llama and return a pre-built, 100% reliable pipeline.
    """
    question_lower = question.lower()
    
    # Count keywords (French + English)
    count_keywords = ['combien', 'how many', 'count', 'total', 'nombre de', 'quel est le nombre', 'total count']
    
    # Unique/distinct keywords that exclude simple count
    unique_keywords = ['different', 'unique', 'distinct', 'différent', 'distincts', 'différents']
    
    has_count = any(kw in question_lower for kw in count_keywords)
    has_unique = any(kw in question_lower for kw in unique_keywords)
    
    return has_count and not has_unique


def _detect_grouping_query(question: str, data_headers: List[str]) -> Optional[Dict[str, Any]]:
    """Detect grouping/analysis queries and determine grouping field.
    
    Returns a dict with grouping configuration if detected:
    {
        'group_by_field': 'field_name',
        'aggregations': ['qteVente', 'totalHT', ...],
        'sort_by': 'field_to_sort_by',
        'sort_order': -1 (descending)
    }
    
    Returns None if not a grouping query.
    """
    question_lower = question.lower()
    
    # Grouping keywords (French + English)
    grouping_keywords = [
        'afficher par', 'afficher les', 'montrer par', 'montrer les',  # French: display by/show by
        'par article', 'par produit', 'par client', 'par catégorie',    # French: by article/product/client/category
        'par mois', 'par période', 'par date',                          # French: by month/period/date
        'show by', 'display by', 'group by', 'grouped by',            # English: show/group/display by
        'breakdown', 'analyse', 'analyze'                              # Other
    ]
    
    has_grouping = any(kw in question_lower for kw in grouping_keywords)
    if not has_grouping:
        return None
    
    # Try to detect which field to group by
    group_field = None
    
    # French field mapping
    french_field_map = {
        'article': 'designation',
        'produit': 'designation',
        'produits': 'designation',
        'articles': 'designation',
        'client': 'code',
        'code': 'code',
        'catégorie': 'code',
        'mois': 'period',
        'période': 'period',
        'month': 'period',
        'period': 'period',
    }
    
    # Find which field was mentioned
    for keyword, field in french_field_map.items():
        if keyword in question_lower and field in data_headers:
            group_field = field
            break
    
    # Default to first meaningful field if not explicitly mentioned
    if not group_field:
        # Prefer 'designation' (article/product) if available
        if 'designation' in data_headers:
            group_field = 'designation'
        elif 'code' in data_headers:
            group_field = 'code'
        elif len(data_headers) > 0:
            # Use first non-ID field
            for field in data_headers:
                if field not in ['_id', 'id', 'endpoint', 'sourceUrl']:
                    group_field = field
                    break
    
    if not group_field:
        return None
    
    # Detect which numeric fields to aggregate (sum)
    numeric_patterns = ['qty', 'quantité', 'total', 'montant', 'price', 'prix', 'ht', 'ttc', 'vente']
    aggregations = []
    for field in data_headers:
        field_lower = field.lower()
        if any(pattern in field_lower for pattern in numeric_patterns):
            if field != group_field:
                aggregations.append(field)
    
    # If no aggregations detected, sum all numeric-looking fields
    if not aggregations:
        aggregations = [f for f in data_headers if f != group_field and f not in ['_id', 'id', 'endpoint', 'sourceUrl']]
    
    # Default aggregations if none found
    if not aggregations:
        aggregations = ['qteVente', 'totalHT', 'totalTTC'] if any(f in data_headers for f in ['qteVente', 'totalHT']) else [data_headers[0]]
    
    return {
        'group_by_field': group_field,
        'aggregations': aggregations[:3],  # Limit to top 3 aggregations
        'sort_by': aggregations[0] if aggregations else group_field,
        'sort_order': -1  # Descending by default
    }



def llama_nosql_query_generator(state: AssistantState) -> AssistantState:

    """Generate MongoDB aggregation pipeline using Llama based on user question.

   

    Receives:

        - question: User's natural language query

        - data_headers: List of field names in the data collection

        - selected_endpoints: Endpoints that were called

        - collection_name: MongoDB collection containing the results

   

    Generates:

        - mongodb_query: Aggregation pipeline (JSON format)

        - query_explanation: What the query does

   

    Returns:

        Updated state with generated query

    """

    question = state.get("question", "")

    data_headers = state.get("data_headers", [])

    errors = state.get("errors", []).copy()

    selected_endpoints = state.get("selected_endpoints", [])

    collection_name = state.get("collection_name", "api_results")

   

    if not question:

        errors.append("No question provided to generate NoSQL query")

        state["errors"] = errors

        state["mongodb_query"] = None

        return state

   

    if not data_headers:

        errors.append("No data headers provided for query generation")

        state["errors"] = errors

        state["mongodb_query"] = None

        return state

   

    # ===== PRE-DETECTION: Simple count queries (100% reliable) =====
    if _is_simple_count_query(question):
        print("[DEBUG] ===== SIMPLE COUNT QUERY DETECTED =====")
        print(f"[DEBUG] Question: {question}")
        print("[DEBUG] Using pre-built count pipeline (bypassing Llama)")
        
        # Return pre-built, guaranteed-correct count pipeline
        pipeline = [{"$group": {"_id": None, "total": {"$sum": 1}}}]
        
        print(f"[DEBUG] Generated Pipeline: {json.dumps(pipeline, indent=2)}")
        print("[DEBUG] ==============================================\n")
        
        state["mongodb_query"] = pipeline
        state["query_explanation"] = "Simple total count of all records"
        state["errors"] = errors
        return state
    
    # ===== PRE-DETECTION: Grouping/analysis queries (high confidence) =====
    grouping_config = _detect_grouping_query(question, data_headers)
    if grouping_config:
        print("[DEBUG] ===== GROUPING QUERY DETECTED =====")
        print(f"[DEBUG] Question: {question}")
        print(f"[DEBUG] Group by field: {grouping_config['group_by_field']}")
        print(f"[DEBUG] Aggregating: {grouping_config['aggregations']}")
        print("[DEBUG] Using pre-built grouping pipeline (bypassing Llama)")
        
        # Build group stage
        group_stage = {
            "_id": f"$record.{grouping_config['group_by_field']}"
        }
        
        # Add aggregations
        for agg_field in grouping_config['aggregations']:
            # Use descriptive names
            agg_name = agg_field.replace('Vente', 'Qty').replace('HT', 'Amount')
            group_stage[agg_name] = {"$sum": f"$record.{agg_field}"}
        
        pipeline = [
            {"$group": group_stage},
            {"$sort": {grouping_config['sort_by']: grouping_config['sort_order']}}
        ]
        
        print(f"[DEBUG] Generated Pipeline: {json.dumps(pipeline, indent=2)}")
        print("[DEBUG] ==============================================\n")
        
        state["mongodb_query"] = pipeline
        state["query_explanation"] = f"Grouped by {grouping_config['group_by_field']}, showing {', '.join(grouping_config['aggregations'])}"
        state["errors"] = errors
        return state
    
    # ===== For all other queries, use Llama =====

    # Build system prompt for Llama

    system_prompt = (

        "You are an expert MongoDB aggregation pipeline generator.\n\n"

        "Your task: Generate a VALID JSON MongoDB aggregation pipeline.\n\n"

        "IMPORTANT: The data structure in MongoDB is nested - each document has a 'record' field containing the actual data.\n"

        "To access fields, use dot notation: '$record.fieldname' (e.g., $record.qteVente, $record.designation)\n\n"

        "SUPPORTED LANGUAGES: English and French queries\n\n"

        "═══ QUERY TYPES ═══\n\n"

        "1. SIMPLE COUNT QUERIES (Single aggregated result):\n"

        "   Keywords: 'combien', 'how many', 'count', 'total', 'nombre de'\n"

        '   Examples:\n'

        '   - FR: "Combien de ventes?" → [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        '   - EN: "How many records?" → [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n\n'

        "2. GROUPING/ANALYSIS QUERIES (Multiple results grouped by field):\n"

        "   Keywords: 'afficher par', 'montrer par', 'show by', 'display by', 'group by'\n"

        "   Examples:\n"

        '   - FR: "Afficher les ventes par articles" → [{"$group": {"_id": "$record.designation", "totalQty": {"$sum": "$record.qteVente"}, "totalAmount": {"$sum": "$record.totalHT"}}}, {"$sort": {"totalAmount": -1}}]\n'

        '   - FR: "Montrer les ventes par client" → [{"$group": {"_id": "$record.code", "qty": {"$sum": "$record.qteVente"}}}, {"$sort": {"qty": -1}}]\n'

        '   - EN: "Show sales by product" → [{"$group": {"_id": "$record.designation", "qty": {"$sum": "$record.qteVente"}}}, {"$sort": {"qty": -1}}]\n\n'

        "CRITICAL FORMATTING RULES:\n"

        '1. EVERY JSON property name MUST be quoted: "$match", "$group", "$project", etc.\n'

        '2. Example: [{"$match": {"record.field": "value"}}, {"$group": {"_id": "$record.field"}}]\n'

        "3. Return ONLY the JSON array itself - no explanations, no markdown, no code blocks\n"

        "4. All strings must be quoted with double quotes\n"

        "5. Use valid JSON syntax: commas between items, proper nesting\n"

        "6. Use dot notation to access nested fields: $record.fieldname\n"

        "7. DO NOT use regex patterns or /pattern/ syntax - use simple field matching only\n"

        "8. For text matching, use exact string values\n\n"

        "Pipeline stages you may use:\n"

        '- {"$match": {"record.field": "value"}} - filter documents by exact match\n'

        '- {"$group": {"_id": "$record.field", "total": {"$sum": "$record.field"}}} - group and aggregate\n'

        '- {"$sort": {"field": -1}} - sort results (-1 for descending, 1 for ascending)\n'

        '- {"$limit": N} - limit results\n'

        '- {"$project": {"field": 1}} - select output fields\n'

    )

   

    # Build user prompt

    headers_str = ", ".join(data_headers)

    user_prompt = (

        f"Question: {question}\n"

        f"Available fields in the nested 'record' field: {headers_str}\n\n"

        "═══ QUERY CLASSIFICATION PRIORITY ═══\n\n"

        "1️⃣ SIMPLE COUNT (returns ONE aggregated result):\n"

        "   Look for: 'combien', 'how many', 'count', 'total', 'nombre de'\n"

        "   Answer: How many items total?\n"

        '   ALWAYS return: [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        "   French examples:\n"

        '   - "Combien de clients?" → [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        '   - "Combien de ventes?" → [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        "   English examples:\n"

        '   - "How many records?" → [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        '   - "Count all items" → [{"$group": {"_id": null, "total": {"$sum": 1}}}]\n\n'

        "2️⃣ GROUPING/ANALYSIS (returns MULTIPLE results grouped by a field):\n"

        "   Look for: 'afficher par', 'montrer par', 'show by', 'display by', 'group by', 'par article', 'par client', etc.\n"

        "   Answer: Show me breakdown/details grouped by a field\n"

        "   French examples:\n"

        '   - "Afficher les ventes par articles" → [{"$group": {"_id": "$record.designation", "qty": {"$sum": "$record.qteVente"}, "totalHT": {"$sum": "$record.totalHT"}}}, {"$sort": {"totalHT": -1}}]\n'

        '   - "Montrer les ventes par client" → [{"$group": {"_id": "$record.code", "totalQty": {"$sum": "$record.qteVente"}}}, {"$sort": {"totalQty": -1}}]\n'

        "   English examples:\n"

        '   - "Show sales by product" → [{"$group": {"_id": "$record.designation", "qty": {"$sum": "$record.qteVente"}}}, {"$sort": {"qty": -1}}]\n'

        '   - "Display breakdown by client" → [{"$group": {"_id": "$record.code", "total": {"$sum": "$record.totalHT"}}}, {"$sort": {"total": -1}}]\n\n'

        "3️⃣ UNIQUE/DIFFERENT COUNT (returns ONE result with count of unique values):\n"

        "   Look for: 'different', 'unique', 'distinct', 'différent', 'distincts', 'combien de différents'\n"

        "   Answer: How many unique/different items?\n"

        '   French examples:\n'

        '   - "Combien de différents articles?" → [{"$group": {"_id": "$record.designation"}}, {"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        '   - "Combien de clients différents?" → [{"$group": {"_id": "$record.code"}}, {"$group": {"_id": null, "total": {"$sum": 1}}}]\n'

        "\n══════════════════════════════════════════════════════════════════\n\n"

        "RULES FOR ALL QUERIES:\n"

        "- Use fields from the 'record' object with dot notation: $record.fieldname\n"

        "- For aggregations (SUM), reference the field: {\"$sum\": \"$record.fieldname\"}\n"

        "- For grouping, reference the field to group by: {\"_id\": \"$record.fieldname\"}\n"

        "- ONLY add $match if the question explicitly asks to filter (e.g., 'where code=ABC')\n"

        "- CRITICAL: Only add $match filters when explicitly requested in the question\n"

        "  • 'show all articles' → NO $match, just $group\n"

        "  • 'show articles where code=ABC' → ADD $match with that code\n"

        "  • 'display sales by articles' → NO $match, just $group and $sort\n\n"

        "DO NOT use regex patterns (/pattern/), use exact field values instead.\n"

        "DO NOT use // comments, /pattern/ syntax, or any non-JSON characters.\n"

        "DO NOT add $match filters unless explicitly asked in the question.\n\n"

        "Generate a MongoDB aggregation pipeline for this question.\n"

        "RESPOND WITH ONLY VALID JSON ARRAY.\n"

        "Start with [ and end with ]. No other text.\n"

        'Example response:\n'

        '[{"$group": {"_id": "$record.designation", "totalQty": {"$sum": "$record.qteVente"}, "totalHT": {"$sum": "$record.totalHT"}}}, {"$sort": {"totalHT": -1}}, {"$limit": 10}]'

    )

   

    # Call Llama to generate query

    try:

        model = config.ollama_model_answer()

       

        # Use streaming chat endpoint, not JSON endpoint (more flexible for this task)

        from utils.api_client import call_ollama_chat

       

        response = call_ollama_chat(model, system_prompt, user_prompt)

       

        if not response:

            errors.append("Llama did not return a response for NoSQL query generation")

            state["errors"] = errors

            state["mongodb_query"] = None

            return state

       

        # Parse the response - extract JSON from response text

        response_text = response.strip()

       

        # Remove markdown code blocks if present

        if response_text.startswith("```"):

            response_text = response_text.split("```")[1]

            if response_text.startswith("json"):

                response_text = response_text[4:]

            response_text = response_text.strip()

       

        # Try to find JSON array in response

        # Look for [ ... ] pattern

        start_idx = response_text.find("[")

        end_idx = response_text.rfind("]")

       

        if start_idx == -1 or end_idx == -1:

            errors.append(f"Llama response did not contain valid JSON array: {response_text[:200]}")

            state["errors"] = errors

            state["mongodb_query"] = None

            return state

       

        json_str = response_text[start_idx:end_idx + 1]

       

        # Try to parse JSON

        try:

            mongodb_pipeline = json.loads(json_str)

        except json.JSONDecodeError:

            # Try to fix common issues: unquoted keys and regex patterns

            import re

           

            # Fix unquoted property names like $match with "$match"

            json_str_fixed = re.sub(r'(\{|\,)\s*(\$\w+)\s*:', r'\1 "\2":', json_str)

           

            # Fix regex patterns: /pattern/ → {"$regex": "pattern"}

            # This is a simple fix for basic patterns - converts /^pattern$/ to proper JSON

            json_str_fixed = re.sub(

                r':\s*/([^/]+)/([gimuy]*)',  # Match :/pattern/flags

                r': {"$regex": "\1"}',  # Replace with {"$regex": "pattern"}

                json_str_fixed

            )

           

            mongodb_pipeline = json.loads(json_str_fixed)

       

        if not isinstance(mongodb_pipeline, list):

            errors.append("Generated MongoDB query is not a list/pipeline")

            state["errors"] = errors

            state["mongodb_query"] = None

            return state

       

        # Debug: Show generated MongoDB query

        print(f"\n[DEBUG] ===== LLAMA MONGODB QUERY GENERATION =====")

        print(f"[DEBUG] Question: {question}")

        print(f"[DEBUG] Available fields: {data_headers}")

        print(f"[DEBUG] Generated MongoDB Pipeline:")

        print(json.dumps(mongodb_pipeline, indent=2, default=str))

        print(f"[DEBUG] ==============================================\n")

       

        state["mongodb_query"] = mongodb_pipeline

        state["mongodb_query_generated"] = True

        state["errors"] = errors

        return state

       

    except json.JSONDecodeError as e:

        errors.append(f"Failed to parse Llama's MongoDB query response: {e}")

        errors.append(f"Llama returned: {json_str[:300] if 'json_str' in locals() else response_text[:300]}")

        state["errors"] = errors

        state["mongodb_query"] = None

        return state

    except Exception as e:

        errors.append(f"Error generating NoSQL query with Llama: {e}")

        state["errors"] = errors

        state["mongodb_query"] = None

        return state