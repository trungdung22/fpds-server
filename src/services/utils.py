from typing import Dict, List, Any, Optional, Tuple
from services.fpds_field_mappings import FPDSFieldMapper


def convert_string_dates_to_isodate(filter_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert string dates in filter to ISODate objects for proper MongoDB comparison
    """
    from datetime import datetime

    def convert_value(value):
        if isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [convert_value(v) for v in value]
        elif isinstance(value, str) and is_date_string(value):
            try:
                # Parse the date string and convert to datetime
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt
            except ValueError:
                return value
        else:
            return value

    return convert_value(filter_dict)


def is_date_string(value: str) -> bool:
    """
    Check if a string looks like a date
    """
    import re
    # Match patterns like "2025-07-01", "2025-07-01T00:00:00.000Z", etc.
    date_patterns = [
        r'^\d{4}-\d{2}-\d{2}$',
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$'
    ]

    for pattern in date_patterns:
        if re.match(pattern, value):
            return True
    return False

def enhance_query_understanding(query: str) -> str:
    """
    Enhance query understanding by adding context and expanding terms
    """
    query_lower = query.lower()
    enhanced_parts = []

    # Add context for service/opportunity searches
    if any(term in query_lower for term in ['opportunity', 'service', 'cybersecurity', 'it', 'construction', 'maintenance', 'consulting', 'training', 'research', 'software', 'hardware', 'supplies', 'security', 'medical']):
        enhanced_parts.append \
            ("SERVICE/OPPORTUNITY SEARCH: This query is looking for specific services or opportunities.")

    # Add context for set-aside searches
    if any(term in query_lower for term in ['8a', 'small business', 'women owned', 'veteran owned', 'minority owned', 'disadvantaged', 'hubzone', 'set aside', 'set-aside']):
        enhanced_parts.append("SET-ASIDE SEARCH: This query involves business set-aside requirements.")

    # Add context for agency searches
    if any(term in query_lower for term in ['nasa', 'dod', 'navy', 'army', 'air force', 'defense', 'homeland security', 'energy', 'health', 'treasury', 'interior', 'agriculture', 'commerce', 'labor', 'transportation', 'education', 'veterans', 'justice', 'state', 'epa', 'gsa', 'ssa', 'opm', 'nrc', 'fcc']):
        enhanced_parts.append("AGENCY SEARCH: This query involves specific federal agencies.")

    # Add context for vendor searches
    if any(term in query_lower for term in ['booz allen', 'boeing', 'lockheed', 'raytheon', 'northrop', 'general dynamics', 'company', 'vendor', 'contractor']):
        enhanced_parts.append("VENDOR SEARCH: This query involves specific vendors or contractors.")

    # Add context for date searches
    if any(term in query_lower for term in ['expiring', 'expired', 'active', 'recent', 'old', 'this year', 'last year', 'next year', '2024', '2025', '2026']):
        enhanced_parts.append("DATE SEARCH: This query involves time-based filtering.")

    # Add context for amount searches
    if any(term in query_lower for term in ['large', 'small', 'million', 'billion', 'thousand', 'high value', 'low value', '$', 'amount', 'value']):
        enhanced_parts.append("AMOUNT SEARCH: This query involves financial value filtering.")

    # Combine enhanced query
    if enhanced_parts:
        enhanced_query = f"{query}\n\nCONTEXT: {'; '.join(enhanced_parts)}"
    else:
        enhanced_query = query

    return enhanced_query


class PromptHelper:

    @classmethod
    def _get_categorized_field_info(self) -> str:
        """
        Get field information organized by category for better filtering
        """
        categories = {}

        # Group fields by category
        for field_name, field_data in FPDSFieldMapper._create_field_mappings().items():
            category = field_data['category']
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'name': field_name,
                'description': field_data['description'],
                'search_terms': field_data['search_terms']
            })

        # Build categorized field info with emphasis on comprehensive searches
        categorized_info = []

        # Prioritize service-related categories first
        priority_categories = ['product_service', 'contract', 'competition', 'entity', 'contracting_office', 'funding',
                               'dates', 'financial']

        for category in priority_categories:
            if category in categories:
                fields = categories[category]
                categorized_info.append(f"\n{category.upper()} FIELDS (use ALL for comprehensive search):")

                # Show more fields for service-related categories
                max_fields = 12 if category in ['product_service', 'contract', 'competition'] else 8

                for field in fields[:max_fields]:
                    search_terms = ', '.join(field['search_terms'][:5])  # Show more search terms
                    categorized_info.append(f"  - {field['name']}: {field['description']} (search: {search_terms})")

        # Add remaining categories
        for category, fields in categories.items():
            if category not in priority_categories:
                categorized_info.append(f"\n{category.upper()} FIELDS:")
                for field in fields[:6]:
                    search_terms = ', '.join(field['search_terms'][:3])
                    categorized_info.append(f"  - {field['name']}: {field['description']} (search: {search_terms})")

        return '\n'.join(categorized_info)

    @classmethod
    def _get_service_search_fields(cls) -> List[str]:
        """
        Get comprehensive list of fields for service/opportunity searches
        """
        return [
            "productservice_code_product_or_service_code_description",
            "nature_of_services",
            "principal_naics_code_north_american_industry_classification_system_description",
            "description_of_requirement",
            "productservice_code_product_or_service_code",
            "principal_naics_code_principal_north_american_industry_classification_system_code",
            "bundled_contract",
            "dod_acquisition_program_dod_acquisition_program",
            "dod_acquisition_program_programsystem_or_equipment_code_description",
            "information_technology_commercial_category",
            "claimant_program_code_claimant_program_code_description"
        ]

    @classmethod
    def _get_set_aside_search_fields(cls) -> List[str]:
        """
        Get comprehensive list of fields for set-aside searches
        """
        return [
            "type_of_set_aside",
            "idv_type_of_set_aside_idv_type_of_set_aside",
            "type_of_set_aside_source_type_of_set_aside_source",
            "local_area_set_aside"
        ]

    @classmethod
    def _get_query_specific_fields(cls, query: str) -> Dict[str, List[str]]:
        """
        Get field suggestions based on query content
        """
        query_lower = query.lower()
        suggestions = {}

        # Service-related terms
        service_terms = ['cybersecurity', 'it', 'computer', 'software', 'hardware', 'construction', 'maintenance',
                         'consulting', 'training', 'research', 'security', 'medical', 'healthcare']
        if any(term in query_lower for term in service_terms):
            suggestions['service_fields'] = cls._get_service_search_fields()

        # Set-aside terms
        set_aside_terms = ['8a', 'small business', 'women owned', 'veteran owned', 'minority owned',
                           'disadvantaged', 'hubzone', 'set aside', 'set-aside']
        if any(term in query_lower for term in set_aside_terms):
            suggestions['set_aside_fields'] = cls._get_set_aside_search_fields()

        # Agency terms
        agency_terms = ['nasa', 'dod', 'navy', 'army', 'air force', 'defense', 'homeland security', 'energy', 'health',
                        'treasury', 'interior', 'agriculture', 'commerce', 'labor', 'transportation', 'education',
                        'veterans', 'justice', 'state', 'epa', 'gsa', 'ssa', 'opm', 'nrc', 'fcc']
        if any(term in query_lower for term in agency_terms):
            suggestions['agency_fields'] = [
                "contracting_office_agency_id_contracting_office_agency_id",
                "contracting_office_agency_id_contracting_office_agency_name",
                "contracting_office_id_contracting_office_id",
                "contracting_office_id_contracting_office_name",
                "funding_agency_id_funding_or_requesting_agency_id",
                "funding_agency_id_funding_or_requesting_agency_name",
                "funding_office_id_funding_or_requesting_office_id",
                "funding_office_id_funding_or_requesting_office_name"
            ]

        return suggestions

    @classmethod
    def create_query_parsing_prompt(cls, query: str, field_info: str) -> str:
        """
        Create prompt for converting natural language to MongoDB filter
        """
        # Get categorized field information for better filtering
        categorized_fields = cls._get_categorized_field_info()

        # Get query-specific field suggestions
        query_specific_fields = cls._get_query_specific_fields(query)

        # Build field suggestions section
        field_suggestions = ""
        if query_specific_fields:
            field_suggestions = "\n\nQUERY-SPECIFIC FIELD SUGGESTIONS:\n"
            for field_type, fields in query_specific_fields.items():
                field_suggestions += f"\n{field_type.replace('_', ' ').title()}:\n"
                for field in fields:
                    field_suggestions += f"  - {field}\n"

        return f"""
    Convert this natural language query to a MongoDB filter for FPDS data:

    Query: "{query}"

    IMPORTANT: When searching for services, opportunities, or specialized terms, use comprehensive OR filters across ALL relevant fields to ensure no relevant records are missed.

    Available FPDS fields organized by category:
    {categorized_fields}{field_suggestions}

    Key filtering strategies:

    1. SERVICE/OPPORTUNITY SEARCHES (cybersecurity, IT, construction, etc.):
       - Use OR filters across ALL service-related fields: {', '.join(cls._get_service_search_fields())}
       - For specialized terms like "cybersecurity", search in ALL text fields that might contain service descriptions
       - Example for cybersecurity: {{"$or": [
           {{"productservice_code_product_or_service_code_description": {{"$regex": "CYBERSECURITY", "$options": "i"}}}},
           {{"nature_of_services": {{"$regex": "CYBERSECURITY", "$options": "i"}}}},
           {{"principal_naics_code_north_american_industry_classification_system_description": {{"$regex": "CYBERSECURITY", "$options": "i"}}}},
           {{"description_of_requirement": {{"$regex": "CYBERSECURITY", "$options": "i"}}}},
           {{"productservice_code_product_or_service_code": {{"$regex": "CYBERSECURITY", "$options": "i"}}}},
           {{"information_technology_commercial_category": {{"$regex": "CYBERSECURITY", "$options": "i"}}}}
       ]}}

    2. AGENCY SEARCHES (NASA, DOD, etc.):
       - Use OR filters across ALL contracting office fields: contracting_office_agency_id_contracting_office_agency_id, contracting_office_agency_id_contracting_office_agency_name, contracting_office_id_contracting_office_id, contracting_office_id_contracting_office_name
       - Use OR filters across ALL funding office fields: funding_agency_id_funding_or_requesting_agency_id, funding_agency_id_funding_or_requesting_agency_name, funding_office_id_funding_or_requesting_office_id, funding_office_id_funding_or_requesting_office_name
       - Example for NASA: {{"$or": [
           {{"contracting_office_agency_id_contracting_office_agency_name": {{"$regex": "NASA", "$options": "i"}}}},
           {{"contracting_office_id_contracting_office_name": {{"$regex": "NASA", "$options": "i"}}}},
           {{"funding_agency_id_funding_or_requesting_agency_name": {{"$regex": "NASA", "$options": "i"}}}},
           {{"funding_office_id_funding_or_requesting_office_name": {{"$regex": "NASA", "$options": "i"}}}}
       ]}}

    3. VENDOR/COMPANY SEARCHES:
       - Use OR filters across ALL entity fields: unique_entity_id_legal_business_name, legal_business_name_legal_business_name
       - Example: {{"$or": [{{"unique_entity_id_legal_business_name": {{"$regex": "Company Name", "$options": "i"}}}}, {{"legal_business_name_legal_business_name": {{"$regex": "Company Name", "$options": "i"}}}}]}}

    4. CONTRACT TYPE SEARCHES:
       - Use OR filters across: type_of_contract, award_type_display
       - Example: {{"$or": [{{"type_of_contract": {{"$regex": "IDIQ", "$options": "i"}}}}, {{"award_type_display": {{"$regex": "IDIQ", "$options": "i"}}}}]}}

    5. SET-ASIDE SEARCHES (8A, small business, etc.):
        - Use OR filters across ONLY these set-aside fields: {', '.join(cls._get_set_aside_search_fields())}
        - Do NOT use "contracting_officers_business_size_selection" for set-aside classification.
        - Example for 8A: {{"$or": [
            {{"type_of_set_aside": {{"$regex": "8A", "$options": "i"}}}},
            {{"idv_type_of_set_aside_idv_type_of_set_aside": {{"$regex": "8A", "$options": "i"}}}},
            {{"type_of_set_aside_source_type_of_set_aside_source": {{"$regex": "8A", "$options": "i"}}}},
            {{"local_area_set_aside": {{"$regex": "8A", "$options": "i"}}}}
        ]}}

    6. DATE SEARCHES:
       - Use appropriate date fields: date_signed_award_completion_date, est_ultimate_completion_date_estimated_ultimate_completion_date
       - Use ISODate format: ISODate('2025-04-30')

    7. AMOUNT SEARCHES:
       - Use: action_obligation_total_obligation_amount, base_and_exercised_options_value_total_base_and_excercised_options_value

    8. LOCATION SEARCHES:
       - Use OR filters across: unique_entity_id_entity_state, principal_place_of_performance_code_principal_place_of_performance_state_code

    9. COMPETITION SEARCHES:
       - Use OR filters across: extent_competed, type_of_set_aside, solicitation_procedures
       - Example for competitive: {{"$or": [
           {{"extent_competed": {{"$regex": "COMPETITIVE", "$options": "i"}}}},
           {{"solicitation_procedures": {{"$regex": "COMPETITIVE", "$options": "i"}}}}
       ]}}

    Date formats: Use ISODate for date comparisons (e.g., ISODate('2026-03-31'))
    Text searches: Use $regex for partial matches (e.g., {{"field": {{"$regex": "NASA", "$options": "i"}}}})
    Amount ranges: Use $gte, $lte for numeric comparisons

    Return a JSON object with the MongoDB filter:
    {{
        "filter": {{
            "$and": [
                {{"$or": [{{"field1": {{"$regex": "value", "$options": "i"}}}}, {{"field2": {{"$regex": "value", "$options": "i"}}}}]}},
                {{"date_field": {{"$gte": "ISODate('2024-01-01')"}}}}
            ]
        }},
        "sort": {{"field": 1}},
        "limit": 100,
        "explanation": "Brief explanation of the filter logic"
    }}

    Examples:
    - "find me CYBERSECURITY opportunity which are set aside 8A" → filter for cybersecurity services (ALL service description fields) AND 8A set-aside (ONLY set-aside fields)
    - "NASA awards expiring in Q2 2026" → filter for NASA agency (ALL contracting and funding office fields) and completion dates in Q2 2026
    - "Booz Allen contracts over $1M" → filter for vendor name (ALL entity fields) and obligation amount > 1000000
    - "IDIQs awarded to Booz Allen" → filter for vendor name (ALL entity fields) and contract type (both type_of_contract and award_type_display)
    - "IT services set aside for small business" → filter for IT services (ALL service fields) AND small business set-aside (ALL set-aside fields)
    - "COMPUTER PROGRAMMING SERVICES opportunity which are set aside 8A" → filter for computer programming services (ALL service fields) AND 8A set-aside (ALL set-aside fields)
    - "NAVY or ARMY related to CYBERSECURITY" → filter for Navy/Army agencies (ALL agency fields) AND cybersecurity services (ALL service fields)

    CRITICAL: Always use comprehensive OR filters when searching for services, entities, or specialized terms to ensure no relevant records are missed. For service searches, include ALL fields that might contain service descriptions.

    Return only the JSON object.
    """