==================================================
Query: find me COMPUTER PROGRAMMING SERVICES opportunity which are set aside 8a -> have reuslt

filter decode:
`
{
  'filter': {
    '$and': [
      {
        '$or': [
          {
            'productservice_code_product_or_service_code_description': {
              '$regex': 'COMPUTER PROGRAMMING SERVICES',
              '$options': 'i'
            }
          },
          {
            'principal_naics_code_north_american_industry_classification_system_description': {
              '$regex': 'COMPUTER PROGRAMMING SERVICES',
              '$options': 'i'
            }
          }
        ]
      },
      {
        '$or': [
          {
            'type_of_set_aside': {
              '$regex': '8A',
              '$options': 'i'
            }
          },
          {
            'idv_type_of_set_aside_idv_type_of_set_aside': {
              '$regex': '8A',
              '$options': 'i'
            }
          }
        ]
      }
    ]
  },
  'sort': {
    
  },
  'limit': 100,
  'explanation': 'Filter for opportunities related to COMPUTER PROGRAMMING SERVICES using product/service code descriptions and NAICS descriptions, with set asides specifically for 8a.'
}
`

==================================================
Query: find me CYBERSECURITY opportunity which are set aside 8A -> failed to find

Filter: {
  'filter': {
    '$and': [
      {
        '$or': [
          {
            'productservice_code_product_or_service_code_description': {
              '$regex': 'CYBERSECURITY',
              '$options': 'i'
            }
          },
          {
            'nature_of_services': {
              '$regex': 'CYBERSECURITY',
              '$options': 'i'
            }
          }
        ]
      },
      {
        '$or': [
          {
            'type_of_set_aside': {
              '$regex': '8A',
              '$options': 'i'
            }
          },
          {
            'idv_type_of_set_aside_idv_type_of_set_aside': {
              '$regex': '8A',
              '$options': 'i'
            }
          }
        ]
      }
    ]
  },
  'sort': {
    
  },
  'limit': 100,
  'explanation': 'Filter for opportunities related to CYBERSECURITY with a set aside type of 8A, using comprehensive OR filters for both the nature of services and set aside fields.'
}

==================================================
Query: Find me opportunity in NAVY or ARMY related to CYBERSECURITY -> find to find 

Filter: {
  'filter': {
    '$and': [
      {
        '$or': [
          {
            'productservice_code_product_or_service_code_description': {
              '$regex': 'CYBERSECURITY',
              '$options': 'i'
            }
          },
          {
            'nature_of_services': {
              '$regex': 'CYBERSECURITY',
              '$options': 'i'
            }
          }
        ]
      },
      {
        '$or': [
          {
            'type_of_set_aside': {
              '$regex': '8A',
              '$options': 'i'
            }
          },
          {
            'idv_type_of_set_aside_idv_type_of_set_aside': {
              '$regex': '8A',
              '$options': 'i'
            }
          }
        ]
      }
    ]
  },
  'sort': {
    
  },
  'limit': 100,
  'explanation': 'Filter for opportunities related to CYBERSECURITY with a set aside type of 8A, using comprehensive OR filters for both the nature of services and set aside fields.'
}


==================================================
Query: find contracts over $1M awarded in Q1 2025 -> Results: 100

Filter: {
  'filter': {
    '$and': [
      {
        '$or': [
          {
            'date_signed_date_signed': {
              '$gte': '2025-01-01',
              '$lt': '2025-04-01'
            }
          },
          {
            'date_signed_period_of_performance_start_date': {
              '$gte': '2025-01-01',
              '$lt': '2025-04-01'
            }
          },
          {
            'period_of_performance_start_date_period_of_performance_start_date': {
              '$gte': '2025-01-01',
              '$lt': '2025-04-01'
            }
          }
        ]
      },
      {
        '$or': [
          {
            'action_obligation_total_obligation_amount': {
              '$gt': 1000000
            }
          },
          {
            'base_and_exercised_options_value_total_base_and_excercised_options_value': {
              '$gt': 1000000
            }
          }
        ]
      }
    ]
  },
  'sort': {
    'date_signed_date_signed': 1
  },
  'limit': 100,
  'explanation': 'Filter for contracts with a total obligation amount over $1M awarded in Q1 2025, using date fields to capture the signing or start of performance within the specified quarter.'
}

==================================================
Query: how many IDIQs awarded to Booz Allen expired by Q3 2025 -> cannot find

Filter: {
  'filter': {
    '$and': [
      {
        '$or': [
          {
            'unique_entity_id_legal_business_name': {
              '$regex': 'BOOZ ALLEN',
              '$options': 'i'
            }
          },
          {
            'legal_business_name_legal_business_name': {
              '$regex': 'BOOZ ALLEN',
              '$options': 'i'
            }
          }
        ]
      },
      {
        '$or': [
          {
            'type_of_contract': {
              '$regex': 'IDIQ',
              '$options': 'i'
            }
          },
          {
            'award_type_display': {
              '$regex': 'IDIQ',
              '$options': 'i'
            }
          }
        ]
      },
      {
        'est_ultimate_completion_date_estimated_ultimate_completion_date': {
          '$lte': '2025-09-30'
        }
      }
    ]
  },
  'sort': {
    
  },
  'limit': 100,
  'explanation': 'Filter for IDIQ contracts awarded to Booz Allen with an estimated ultimate completion date on or before the end of Q3 2025.'
}