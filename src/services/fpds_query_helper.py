import json
import logging
import os
import sys
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta



try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
from services.mongo_service import FPDSMongoDBService
from services.fpds_field_mappings import FPDSFieldMapper
from conf.settings import Settings
from services.utils import enhance_query_understanding, PromptHelper, convert_string_dates_to_isodate
# Add parent directory to path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
            # Print JSON to console for debugging/inspection
            try:
                print(json.dumps(results, indent=2, default=str))
            except Exception as json_err:
                logger.warning(f"Failed to print JSON response: {json_err}")

            # Step 3: Format results with LLM for human-readable response
            formatted_response = self._format_results_with_llm(
                natural_language_query, results, mongo_filter
            )
            
            response_dict = {
                "query": natural_language_query,
                "mongo_filter": mongo_filter,
                "results_count": len(results),
                "formatted_response": formatted_response,
                "raw_results": results[:10]  # Limit raw results for response
            }
            return response_dict

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
        enhanced_query = enhance_query_understanding(query)
        
        # Get field information for LLM
        field_info = self._get_field_info_for_llm()
        
        # Create prompt for LLM
        prompt = PromptHelper.create_query_parsing_prompt(enhanced_query, field_info)
        
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
            # Enforce allowed set-aside fields only
            filter_dict = self._sanitize_set_aside_filters(filter_dict)
            return filter_dict
            
        except Exception as e:
            logger.error(f"LLM query parsing failed: {e}")
        return {}

    def _sanitize_set_aside_filters(self, filter_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce that set-aside matching (e.g., 8A) only uses allowed set-aside fields.
        Removes any conditions on disallowed fields such as
        "contracting_officers_business_size_selection".

        Allowed fields:
        - type_of_set_aside
        - idv_type_of_set_aside_idv_type_of_set_aside
        - type_of_set_aside_source_type_of_set_aside_source
        - local_area_set_aside
        """
        if not isinstance(filter_config, dict):
            return filter_config

        allowed_fields = {
            "type_of_set_aside",
            "idv_type_of_set_aside_idv_type_of_set_aside",
            "type_of_set_aside_source_type_of_set_aside_source",
            "local_area_set_aside",
        }
        disallowed_fields = {"contracting_officers_business_size_selection"}

        def sanitize(node: Any) -> Any:
            # Recursively sanitize a filter node
            if isinstance(node, list):
                sanitized_list = [sanitize(item) for item in node]
                # Drop empty dicts produced by removals
                sanitized_list = [item for item in sanitized_list if item not in (None, {}, [])]
                return sanitized_list

            if isinstance(node, dict):
                new_obj: Dict[str, Any] = {}
                for key, value in node.items():
                    # Pass through logical operators with recursive sanitize
                    if key in ("$and", "$or", "$nor"):
                        sanitized_value = sanitize(value)
                        # If OR/NOR becomes empty, drop it entirely to avoid filtering out all results
                        if key in ("$or", "$nor") and not sanitized_value:
                            continue
                        # If AND becomes empty, it is a no-op, so drop
                        if key == "$and" and not sanitized_value:
                            continue
                        new_obj[key] = sanitized_value
                        continue

                    # If this is a field condition
                    if key in disallowed_fields:
                        # Drop any conditions on disallowed fields entirely
                        continue

                    # Keep allowed set-aside fields and any other non-set-aside fields
                    # If the key looks like a set-aside field but is not in allowed list, drop it
                    if "set_aside" in key and key not in allowed_fields:
                        continue

                    new_obj[key] = sanitize(value)

                return new_obj

            return node

        if "filter" in filter_config and isinstance(filter_config["filter"], (dict, list)):
            filter_config["filter"] = sanitize(filter_config["filter"]) or {}
        return filter_config

    def _get_field_info_for_llm(self) -> str:
        """
        Get field information for LLM prompt
        """
        field_info = []
        for field_name, field_data in self.field_mapper.field_mappings.items():
            field_info.append(f"- {field_name}: {field_data['description']} ({field_data['category']})")
        
        return "\n".join(field_info[:80])  # Limit to first 50 fields

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
            filter_dict = convert_string_dates_to_isodate(filter_dict)
            
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
        openai_api_key=Settings.open_api_key
    )
    
    try:
        # Test queries
        test_queries = [
            # "how many IDIQs awarded to Booz Allen expired by Q3 2025",
            # "what are the largest contracts awarded to Boeing in 2024",
            # "show me all NASA awards expiring in Q3 2025",
            # "find contracts over $1M awarded in Q1 2025",
            # "Find me opportunity in NAVY or ARMY related to CYBERSECURITY",
            # "find me CYBERSECURITY opportunity which are set aside 8A",
            # "Find me SUPPORT opportunities expiring bet Jan to June 2026 which are 8a set aside",
            # "Find me cybersecurity opportunities expiring bet Jan to June 2026 which are 8a set aside",
            # "Search CLOUD RFPs expiring between Jan to June 2026 from $1m to $5m",
            # "Search staffing RFPs expiring between Jan to June 2026 from $1m to $5m",
            # "Search 8a RFPs expiring between Jan to June 2026 from $1m to $5m in Army"
            "Search 8a RFPs expiring between Jan to June 2026 from $1m to $5m in Navy"
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