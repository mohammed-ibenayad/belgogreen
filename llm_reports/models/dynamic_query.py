from odoo import models, fields, api
import logging
from openai import OpenAI
import json
import re
from datetime import datetime
from functools import lru_cache

_logger = logging.getLogger(__name__)

class DynamicQueryReport(models.TransientModel):
    _name = 'dynamic.query.report'
    _description = 'Dynamic Query Report'

    user_input = fields.Text(string="Enter your query", required=False)
    save_filter_checkbox = fields.Boolean(string="Save Filter", help="Check this box to save the filter for future use.")

    def clean_llm_response(self, content):
        content = re.sub(r'```json\s*|\s*```', '', content)
        return content.strip()

    @lru_cache(maxsize=32)  # Cache results to avoid repeated queries
    def get_model_fields(self, model_name):
        try:
            if model_name not in self.env:
                raise ValueError(f"Invalid model name: {model_name}")
            
            model = self.env[model_name]
            fields_info = model.fields_get()
            
            # Format fields with descriptions and related models (if applicable)
            fields_description = "\n".join([
                f"{field_name}: {field_info['type']} "
                f"({field_info.get('string', 'No description')})"
                f"{' (Related model: ' + field_info['relation'] + ')' if field_info['type'] in ('many2one', 'one2many', 'many2many') and 'relation' in field_info else ''}"
                for field_name, field_info in fields_info.items()
            ])
            
            return fields_description
        
        except Exception as e:
            _logger.error(f"Failed to retrieve fields for model {model_name}: {str(e)}")
            raise ValueError(f"Failed to retrieve fields for model {model_name}: {str(e)}")

    def send_to_llm(self, messages, temperature=0.1):

        """Send messages to LLM using securely stored API key."""
        try:
            # Get API key from system parameters
            api_key = self.env['ir.config_parameter'].sudo().get_param('natural_query.llm_api_key')
            base_url = self.env['ir.config_parameter'].sudo().get_param(
                'natural_query.llm_base_url', 
                default='https://api.deepseek.com'
            )
            
            if not api_key:
                raise ValueError("LLM API Key not configured. Please set it in System Parameters.")
                
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
    
            _logger.info("Sending messages to LLM")  # Don't log the actual messages for security
    
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            _logger.info("Received response from LLM")  # Don't log the actual response
            
            cleaned_content = self.clean_llm_response(content)
            
            try:
                parsed_response = json.loads(cleaned_content)
                return parsed_response
                
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")
            
        except Exception as e:
            _logger.error(f"API request failed: {str(e)}")
            raise ValueError(f"API request failed: {str(e)}")        

    def discover_model_name(self, user_input):
        # First step: Ask the LLM to identify the model name
        system_prompt = {
            "role": "system",
            "content": """You are a helpful assistant that identifies the Odoo model name from a natural language query. Return only the JSON response with a single key 'model' containing the model name. If you cannot determine the model, return an empty JSON object {}."""
        }

        user_message = {"role": "user", "content": user_input}

        llm_response = self.send_to_llm([system_prompt, user_message], temperature=0.1)
        model_name = llm_response.get('model')

        if not model_name:
            _logger.info("No model name identified by the LLM.")
            return None

        _logger.info(f"Discovered model name: {model_name}")
        return model_name

    def generate_domain_filter(self, user_input, model_name):
        try:
            # Fetch today's date for dynamic date-related queries
            today = fields.Date.today().strftime('%Y-%m-%d')
            
            # Fetch the fields of the identified model (with caching)
            fields_description = self.get_model_fields(model_name)
            
            # Construct the system prompt with the model's fields and descriptions
            system_prompt = {
                "role": "system",
                "content": f"""Fact: Today's date is {today}

You are a helpful assistant that converts natural language queries into Odoo domain filters. Return only the JSON response with 'model', 'domain', and 'filter_name' keys. Use list syntax with square brackets [] for conditions, like: ["field", "operator", "value"]. If you want to return all records, return an empty list [] as the domain value.

Domain Construction Patterns:
1. Basic Comparison:
   - Equality: ["field", "=", value]
   - Inequality: ["field", "!=", value]
   - Greater/Less: ["field", ">", value], ["field", "<", value]
   - List membership: ["field", "in", [val1, val2]]

2. Text Search:
   - Case insensitive: ["name", "ilike", "search_term"]
   - Case sensitive: ["name", "like", "search_term"]
   - Negation: ["name", "not ilike", "search_term"]

3. Date Ranges:
   - Single range: ["date", ">=", "start_date"], ["date", "<=", "end_date"]
   - Multiple ranges (OR): ["|", "&", ["date", ">=", "range1_start"], ["date", "<=", "range1_end"],
                               "&", ["date", ">=", "range2_start"], ["date", "<=", "range2_end"]]

4. Special Values:
   - Null checks: ["field", "=", False]
   - Not null: ["field", "!=", False]

5. Logical Operators:
   - AND (implicit): [["field1", "=", val1], ["field2", "=", val2]]
   - OR: ["|", ["field1", "=", val1], ["field2", "=", val2]]
   - Multiple OR: ["|", "|", ["field1", "=", val1], ["field2", "=", val2], ["field3", "=", val3]]

Do not include any markdown formatting or code blocks in your response.

The model '{model_name}' has the following fields:
{fields_description}
"""
            }

            # Send the user input and system prompt to the LLM
            user_message = {"role": "user", "content": user_input}
            llm_response = self.send_to_llm([system_prompt, user_message], temperature=0.1)
            
            return llm_response
        
        except Exception as e:
            _logger.error(f"Failed to generate domain filter: {str(e)}")
            raise ValueError(f"Failed to generate domain filter: {str(e)}")

    def save_filter(self, model_name, domain, filter_name):
        """Save the domain as a filter in Odoo and return the filter ID."""
        try:
            if not filter_name:
                raise ValueError("Filter name is required to save the filter.")
            
            # Create a new filter record
            filter_record = self.env['ir.filters'].create({
                'name': filter_name,
                'model_id': model_name,
                'domain': domain,
                'user_id': self.env.user.id,
                'is_default': False,
                'active': True,
            })
            
            _logger.info(f"Filter '{filter_name}' saved successfully.")
            return filter_record.id  # Return the ID of the created filter
        
        except Exception as e:
            _logger.error(f"Failed to save filter: {str(e)}")
            raise ValueError(f"Failed to save filter: {str(e)}")

    @api.onchange('user_input')
    def _onchange_user_input(self):
        if self.user_input and self.user_input.endswith('\n'):
            self.user_input = self.user_input.rstrip()
            return self.process_input()

    def process_input(self):
        try:
            if not self.user_input or self.user_input.strip() == '':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Warning',
                        'message': 'Please enter a query before submitting.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
    
            # Step 1: Discover the model name
            model_name = self.discover_model_name(self.user_input)
            if not model_name:
                raise ValueError("Unable to identify the model from the query.")
    
            # Step 2: Generate the domain filter using the discovered model name
            llm_response = self.generate_domain_filter(self.user_input, model_name)
            
            domain_filter = llm_response.get('domain')
            filter_name = llm_response.get('filter_name')
            
            if domain_filter is None:
                raise ValueError(f"Invalid response format: {llm_response}")
            
            model = self.env[model_name]
            records = model.search(domain_filter)
            
            # Step 3: Save the filter if the user checked the box
            filter_id = None
            if self.save_filter_checkbox and filter_name:
                filter_id = self.save_filter(model_name, domain_filter, filter_name)
            
            # Step 4: Return the action with the filter applied and modified target
            action = {
                'type': 'ir.actions.act_window',
                'name': f'{model._description or model._name} - Search Results ({len(records)} records)',
                'res_model': model_name,
                'view_mode': 'list,form',
                'domain': domain_filter,
                'target': 'main',
                'flags': {'mode': 'primary'}
            }
    
            # If a filter was created, pass its ID to the action context
            if filter_id:
                action['context'] = {
                    'search_default_filter_id': filter_id,
                }
            
            return action
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Unable to process your query at this time. Please try again later.',
                    'type': 'danger',
                    'sticky': True,
                }
            }