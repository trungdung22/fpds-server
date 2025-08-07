import json
import logging
import os
import sys
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

# Add parent directory to path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mongo_service import FPDSMongoDBService
from services.fpds_field_mappings import FPDSFieldMapper

try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FPDSQueryHelper:
    """
    Query Helper for FPDS data - manages field mappings and MongoDB operations
    """
    
    def __init__(self, 
                 mongo_service: Optional[FPDSMongoDBService] = None,
                 field_mapper: Optional[FPDSFieldMapper] = None,
                 openai_api_key: Optional[str] = None,
                 model: str = "gpt-4o"):
        
        # Initialize components
        self.mongo_service = mongo_service or FPDSMongoDBService()
        self.field_mapper = field_mapper or FPDSFieldMapper()
        
        # Initialize OpenAI
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.openai_client = None
        
        if self.api_key and openai:
            try:
                self.openai_client = OpenAI(api_key=self.api_key)
                logger.info(f"FPDS Query Helper initialized with model: {model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.openai_client = None
        else:
            logger.warning("No OpenAI API key provided. Query formatting will be limited.")
    
    def query(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Main method to process natural language query and return formatted results
        
        Args:
            natural_language_query: Natural language query string
            
        Returns:
            Dictionary containing query results and formatted response
        """
        try:
            # Step 1: Parse natural language to MongoDB filter using field mapper and LLM
            mongo_filter = self._parse_query_to_filter(natural_language_query)
            
            # Step 2: Execute MongoDB query using mongo service
            results = self._execute_mongo_query(mongo_filter)
            
            # Step 3: Format results with LLM for human-readable response
            formatted_response = self._format_results_with_llm(
                natural_language_query, results, mongo_filter
            )
            
            return {
                "query": natural_language_query,
                "mongo_filter": mongo_filter,
                "results_count": len(results),
                "formatted_response": formatted_response,
                "raw_results": results[:10]  # Limit raw results for response
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "error": str(e),
                "query": natural_language_query,
                "results_count": 0,
                "formatted_response": f"Error processing query: {str(e)}"
            }
    
    def _parse_query_to_filter(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language query to MongoDB filter using field mapper and LLM
        """
        # Preprocess query to enhance understanding
        enhanced_query = self._enhance_query_understanding(query)
        
        # Get field information for LLM
        field_info = self._get_field_info_for_llm()
        
        # Create prompt for LLM
        prompt = self._create_query_parsing_prompt(enhanced_query, field_info)
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at converting natural language queries to MongoDB filters for FPDS (Federal Procurement Data System) data. Focus on comprehensive searches that capture all relevant records."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            # Parse the response
            filter_dict = self._parse_llm_filter_response(response.choices[0].message.content)
            return filter_dict
            
        except Exception as e:
            logger.error(f"LLM query parsing failed: {e}")
        return {}

    def _enhance_query_understanding(self, query: str) -> str:
        """
        Enhance query understanding by adding context and expanding terms
        """
        query_lower = query.lower()
        enhanced_parts = []
        
        # Add context for service/opportunity searches
        if any(term in query_lower for term in ['opportunity', 'service', 'cybersecurity', 'it', 'construction', 'maintenance', 'consulting', 'training', 'research', 'software', 'hardware', 'supplies', 'security', 'medical']):
            enhanced_parts.append("SERVICE/OPPORTUNITY SEARCH: This query is looking for specific services or opportunities.")
        
        # Add context for set-aside searches
        if any(term in query_lower for term in ['8a', '8a', 'small business', 'women owned', 'veteran owned', 'minority owned', 'disadvantaged', 'hubzone', 'set aside', 'set-aside']):
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

    def _get_query_specific_fields(self, query: str) -> Dict[str, List[str]]:
        """
        Get field suggestions based on query content
        """
        query_lower = query.lower()
        suggestions = {}
        
        # Service-related terms
        service_terms = ['cybersecurity', 'it', 'computer', 'software', 'hardware', 'construction', 'maintenance', 'consulting', 'training', 'research', 'security', 'medical', 'healthcare']
        if any(term in query_lower for term in service_terms):
            suggestions['service_fields'] = self._get_service_search_fields()
        
        # Set-aside terms
        set_aside_terms = ['8a', '8a', 'small business', 'women owned', 'veteran owned', 'minority owned', 'disadvantaged', 'hubzone', 'set aside', 'set-aside']
        if any(term in query_lower for term in set_aside_terms):
            suggestions['set_aside_fields'] = self._get_set_aside_search_fields()
        
        # Agency terms
        agency_terms = ['nasa', 'dod', 'navy', 'army', 'air force', 'defense', 'homeland security', 'energy', 'health', 'treasury', 'interior', 'agriculture', 'commerce', 'labor', 'transportation', 'education', 'veterans', 'justice', 'state', 'epa', 'gsa', 'ssa', 'opm', 'nrc', 'fcc']
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

    def _get_service_search_fields(self) -> List[str]:
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

    def _get_set_aside_search_fields(self) -> List[str]:
        """
        Get comprehensive list of fields for set-aside searches
        """
        return [
            "type_of_set_aside",
            "idv_type_of_set_aside_idv_type_of_set_aside",
            "contracting_officers_business_size_selection",
            "type_of_set_aside_source_type_of_set_aside_source",
            "sbirsttr",
            "fair_opportunitylimited_sources",
            "local_area_set_aside"
        ]

    def _get_field_info_for_llm(self) -> str:
        """
        Get field information for LLM prompt
        """
        field_info = []
        for field_name, field_data in self.field_mapper.field_mappings.items():
            field_info.append(f"- {field_name}: {field_data['description']} ({field_data['category']})")
        
        return "\n".join(field_info[:80])  # Limit to first 50 fields

    def _create_query_parsing_prompt(self, query: str, field_info: str) -> str:
        """
        Create prompt for converting natural language to MongoDB filter
        """
        # Get categorized field information for better filtering
        categorized_fields = self._get_categorized_field_info()
        
        # Get query-specific field suggestions
        query_specific_fields = self._get_query_specific_fields(query)
        
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
       - Use OR filters across ALL service-related fields: {', '.join(self._get_service_search_fields())}
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
       - Use OR filters across ALL set-aside fields: {', '.join(self._get_set_aside_search_fields())}
       - Example for 8A: {{"$or": [
           {{"type_of_set_aside": {{"$regex": "8A", "$options": "i"}}}},
           {{"idv_type_of_set_aside_idv_type_of_set_aside": {{"$regex": "8A", "$options": "i"}}}},
           {{"contracting_officers_business_size_selection": {{"$regex": "8A", "$options": "i"}}}},
           {{"type_of_set_aside_source_type_of_set_aside_source": {{"$regex": "8A", "$options": "i"}}}}
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
    - "find me CYBERSECURITY opportunity which are set aside 8A" → filter for cybersecurity services (ALL service description fields) AND 8A set-aside (ALL set-aside fields)
    - "NASA awards expiring in Q2 2026" → filter for NASA agency (ALL contracting and funding office fields) and completion dates in Q2 2026
    - "Booz Allen contracts over $1M" → filter for vendor name (ALL entity fields) and obligation amount > 1000000
    - "IDIQs awarded to Booz Allen" → filter for vendor name (ALL entity fields) and contract type (both type_of_contract and award_type_display)
    - "IT services set aside for small business" → filter for IT services (ALL service fields) AND small business set-aside (ALL set-aside fields)
    - "COMPUTER PROGRAMMING SERVICES opportunity which are set aside 8A" → filter for computer programming services (ALL service fields) AND 8A set-aside (ALL set-aside fields)
    - "NAVY or ARMY related to CYBERSECURITY" → filter for Navy/Army agencies (ALL agency fields) AND cybersecurity services (ALL service fields)

    CRITICAL: Always use comprehensive OR filters when searching for services, entities, or specialized terms to ensure no relevant records are missed. For service searches, include ALL fields that might contain service descriptions.

    Return only the JSON object.
    """

    def _get_categorized_field_info(self) -> str:
        """
        Get field information organized by category for better filtering
        """
        categories = {}

        # Group fields by category
        for field_name, field_data in self.field_mapper.field_mappings.items():
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
        priority_categories = ['product_service', 'contract', 'competition', 'entity', 'contracting_office', 'funding', 'dates', 'financial']
        
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
    
    def _parse_llm_filter_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract MongoDB filter
        """
        try:
            # Clean up the response to handle MongoDB-specific syntax
            cleaned_response = self._clean_mongodb_response(response)
            
            # Extract JSON from response - handle markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(cleaned_response)
            
            # Validate and return filter
            if "filter" in result:
                return result
            else:
                logger.warning("Invalid filter response from LLM")
                return {"filter": {}, "explanation": "Failed to parse LLM response"}
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM filter response: {e}")
            logger.error(f"Response: {response}")
            return {"filter": {}, "explanation": "Failed to parse response"}
    
    def _clean_mongodb_response(self, response: str) -> str:
        """
        Clean up MongoDB-specific syntax in the response for JSON parsing
        """
        # Remove markdown code blocks if present
        cleaned = re.sub(r'```(?:json)?\s*', '', response)
        cleaned = re.sub(r'\s*```', '', cleaned)
        
        # Replace ISODate() with string format - handle both single and double quotes
        # This converts ISODate('2026-04-01') to "2026-04-01" (not ""2026-04-01"")
        cleaned = re.sub(r'ISODate\([\'"]([^\'"]+)[\'"]\)', r'"\1"', cleaned)
        
        # Also handle ISODate without quotes inside
        cleaned = re.sub(r'ISODate\(([^)]+)\)', r'"\1"', cleaned)
        
        # Replace other MongoDB-specific syntax
        cleaned = re.sub(r'ObjectId\([\'"]([^\'"]+)[\'"]\)', r'"\1"', cleaned)
        
        # Handle any remaining MongoDB operators that might cause JSON parsing issues
        cleaned = re.sub(r'(\$[a-zA-Z]+):\s*', r'"\1": ', cleaned)
        
        # Fix double quotes issue - replace ""text"" with "text"
        cleaned = re.sub(r'""([^"]+)""', r'"\1"', cleaned)
        
        # Convert regex search terms to uppercase for better matching
        # This converts patterns like "Navy" to "NAVY" in regex searches
        def uppercase_regex_match(match):
            # Extract the regex pattern from the match
            pattern = match.group(1)
            # Convert to uppercase
            return f'"$regex": "{pattern.upper()}"'
        
        # Find and convert regex patterns to uppercase
        cleaned = re.sub(r'"\$regex":\s*"([^"]+)"', uppercase_regex_match, cleaned)
        
        # Debug logging
        logger.debug(f"Original response: {response}")
        logger.debug(f"Cleaned response: {cleaned}")
        
        return cleaned

    def _execute_mongo_query(self, filter_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute MongoDB query using the mongo service
        """
        try:
            filter_dict = filter_config.get("filter", {})
            sort_dict = filter_config.get("sort", {"date_signed_award_completion_date": -1})
            limit = filter_config.get("limit", 100)
            
            # Convert string dates to ISODate objects for proper MongoDB comparison
            filter_dict = self._convert_string_dates_to_isodate(filter_dict)
            
            # Execute query using mongo service collection
            cursor = self.mongo_service.collection.find(filter_dict)
            
            if sort_dict:
                cursor = cursor.sort(list(sort_dict.items()))
            
            if limit:
                cursor = cursor.limit(limit)
            
            results = list(cursor)
            
            # Ensure award ID fields are present for citations
            results = self.field_mapper.ensure_award_id_in_results(results)
            
            logger.info(f"Query returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error executing MongoDB query: {e}")
            return []
    
    def _convert_string_dates_to_isodate(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert string dates in filter to ISODate objects for proper MongoDB comparison
        """
        from datetime import datetime
        
        def convert_value(value):
            if isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [convert_value(v) for v in value]
            elif isinstance(value, str) and self._is_date_string(value):
                try:
                    # Parse the date string and convert to datetime
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt
                except ValueError:
                    return value
            else:
                return value
        
        return convert_value(filter_dict)
    
    def _is_date_string(self, value: str) -> bool:
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
    
    def _format_results_with_llm(self, 
                                original_query: str, 
                                results: List[Dict[str, Any]], 
                                filter_config: Dict[str, Any]) -> str:
        """
        Format query results using LLM with citations
        """
        # Prepare results for LLM
        results_summary = self._prepare_results_for_llm(results)
        
        prompt = f"""
Format the following FPDS query results into a clear, structured response with citations.

Original Query: "{original_query}"
Query Filter: {filter_config.get('explanation', 'N/A')}
Results Count: {len(results)}

Results Summary:
{results_summary}

Please provide a structured response that includes:
1. A clear answer to the original query
2. Key statistics (count, total value, date ranges, etc.)
3. Notable examples with citations using award IDs in format: "Award ID: award_id_agency_id-award_id_procurement_identifier"
4. Any relevant insights or patterns

For each example, include:
- Contract title/description
- Contract type
- Contract date
- Award ID citation
- Key details relevant to the query

Format the response in a clear, professional manner suitable for business reporting.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert analyst specializing in federal procurement data. Provide clear, accurate responses with proper citations using award IDs."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM formatting failed: {e}")

    def _prepare_results_for_llm(self, results: List[Dict[str, Any]]) -> str:
        """
        Prepare results summary for LLM processing
        """
        if not results:
            return "No results found."
        
        summary = []
        
        # Calculate statistics
        total_obligation = sum(
            float(r.get("action_obligation_total_obligation_amount", 0)) 
            for r in results 
            if r.get("action_obligation_total_obligation_amount")
        )
        
        agencies = set()
        vendors = set()
        completion_dates = []
        
        for result in results[:20]:  # Limit for LLM processing
            # Agency
            agency = result.get("contracting_office_agency_id_contracting_office_agency_name", "Unknown")
            agencies.add(agency)
            
            # Vendor
            vendor = result.get("unique_entity_id_legal_business_name", "Unknown")
            vendors.add(vendor)
            
            # Completion date
            completion_date = result.get("date_signed_award_completion_date")
            if completion_date:
                completion_dates.append(completion_date)
            
            # Add sample record with award ID citation
            award_id = f"{result.get('award_id_agency_id', 'N/A')}-{result.get('award_id_procurement_identifier', 'N/A')}"
            contract_type = result.get("type_of_contract", "Unknown")
            contract_date = result.get("date_signed_date_signed", "Unknown")
            amount = result.get("action_obligation_total_obligation_amount", 0)
            
            summary.append(f"Award ID: {award_id}, Agency: {agency}, Vendor: {vendor}, Type: {contract_type}, Date: {contract_date}, Amount: ${amount:,.0f}")
        
        stats = f"""
Statistics:
- Total Results: {len(results)}
- Total Obligation: ${total_obligation:,.0f}
- Unique Agencies: {len(agencies)}
- Unique Vendors: {len(vendors)}
- Date Range: {min(completion_dates) if completion_dates else 'N/A'} to {max(completion_dates) if completion_dates else 'N/A'}

Sample Results:
{chr(10).join(summary)}
"""
        
        return stats

    # Convenience methods for common queries
    def get_contracts_by_agency(self, agency_name: str, limit: int = 100) -> Dict[str, Any]:
        """Get contracts by agency name"""
        query = f"contracts awarded by {agency_name}"
        result = self.query(query)
        result['raw_results'] = result['raw_results'][:limit]
        return result
    
    def get_contracts_by_vendor(self, vendor_name: str, limit: int = 100) -> Dict[str, Any]:
        """Get contracts by vendor name"""
        query = f"contracts awarded to {vendor_name}"
        result = self.query(query)
        result['raw_results'] = result['raw_results'][:limit]
        return result
    
    def get_contracts_by_date_range(self, start_date: str, end_date: str, limit: int = 100) -> Dict[str, Any]:
        """Get contracts by date range"""
        query = f"contracts signed between {start_date} and {end_date}"
        result = self.query(query)
        result['raw_results'] = result['raw_results'][:limit]
        return result
    
    def get_contracts_by_amount_range(self, min_amount: float, max_amount: float, limit: int = 100) -> Dict[str, Any]:
        """Get contracts by amount range"""
        query = f"contracts between ${min_amount:,.0f} and ${max_amount:,.0f}"
        result = self.query(query)
        result['raw_results'] = result['raw_results'][:limit]
        return result
    
    def get_expiring_contracts(self, agency_name: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get contracts expiring soon"""
        if agency_name:
            query = f"{agency_name} contracts expiring soon"
        else:
            query = "contracts expiring soon"
        
        result = self.query(query)
        result['raw_results'] = result['raw_results'][:limit]
        return result
    
    def close(self):
        """
        Close database connections
        """
        if self.mongo_service:
            self.mongo_service.close()
        logger.info("FPDS Query Helper connections closed")


# Example usage
if __name__ == "__main__":
    import os
    
    # Initialize the query helper
    query_helper = FPDSQueryHelper(
        openai_api_key=""
    )
    
    try:
        # Test queries
        test_queries = [
            # "how many IDIQs awarded to Booz Allen expired by Q3 2025",
            # "what are the largest contracts awarded to Boeing in 2024",
            # "show me all NASA awards expiring in Q3 2025",
            # "find contracts over $1M awarded in Q1 2025",
            "Find me opportunity in NAVY or ARMY related to CYBERSECURITY",
            # "find me CYBERSECURITY opportunity which are set aside 8A",
            # "find me COMPUTER PROGRAMMING SERVICES opportunity which are set aside 8a",
        ]
        
        for query in test_queries:
            print(f"\n{'='*50}")
            print(f"Query: {query}")
            print(f"{'='*50}")
            
            result = query_helper.query(query)
            
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Results: {result['results_count']}")
                print(f"Filter: {result['mongo_filter']}")
                print(f"\nFormatted Response:\n{result['formatted_response']}")
    
    finally:
        query_helper.close() 