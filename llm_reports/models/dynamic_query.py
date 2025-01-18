from odoo import models, fields, api
import logging
from openai import OpenAI
import json
import re
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class DynamicQueryReport(models.TransientModel):
    _name = 'dynamic.query.report'
    _description = 'Dynamic Query Report'

    user_input = fields.Text(string="Enter your query", required=True)

    def clean_llm_response(self, content):
        content = re.sub(r'```json\s*|\s*```', '', content)
        return content.strip()

    def get_model_fields(self, model_name):
        if model_name not in self.env:
            raise ValueError(f"Invalid model name: {model_name}")
        model = self.env[model_name]
        fields_info = model.fields_get()
        fields_description = "\n".join([f"{field_name}: {field_info['type']}" for field_name, field_info in fields_info.items()])
        return fields_description

    def send_to_llm(self, messages, temperature=0.1):
        api_key = "sk-069b3d69eeb04fde960b27182745ba4d"
        
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )

            _logger.info(f"Sending messages to LLM: {messages}")

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            _logger.info(f"Raw LLM response: {content}")
            
            cleaned_content = self.clean_llm_response(content)
            
            try:
                parsed_response = json.loads(cleaned_content)
                _logger.info(f"Parsed response: {parsed_response}")
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

    def adjust_date_filters(self, domain):
        """
        Adjust date filters in the domain to include the full day.
        Example: [('create_date', '=', '2023-10-15')] -> [('create_date', '>=', '2023-10-15 00:00:00'), ('create_date', '<=', '2023-10-15 23:59:59')]
        """
        adjusted_domain = []
        for condition in domain:
            if isinstance(condition, (list, tuple)) and len(condition) == 3:
                field, operator, value = condition
                if isinstance(value, str) and value.count('-') == 2:  # Check if the value is a date string
                    if operator == '=':
                        # Replace '=' with a range to cover the entire day
                        start_of_day = f"{value} 00:00:00"
                        end_of_day = f"{value} 23:59:59"
                        adjusted_domain.extend([
                            (field, '>=', start_of_day),
                            (field, '<=', end_of_day)
                        ])
                        continue
            adjusted_domain.append(condition)
        return adjusted_domain

    def generate_domain_filter(self, user_input, model_name):
        # Second step: Generate the domain filter using the discovered model name
        today = fields.Date.today()
        yesterday = today - timedelta(days=1)

        # Format dates for the domain
        today_start = f"{today.strftime('%Y-%m-%d')} 00:00:00"
        today_end = f"{today.strftime('%Y-%m-%d')} 23:59:59"
        yesterday_start = f"{yesterday.strftime('%Y-%m-%d')} 00:00:00"
        yesterday_end = f"{yesterday.strftime('%Y-%m-%d')} 23:59:59"

        # Construct the domain for "today or yesterday"
        domain = [
            "|",
            "&",
            ["start", ">=", today_start],
            ["start", "<=", today_end],
            "&",
            ["start", ">=", yesterday_start],
            ["start", "<=", yesterday_end]
        ]

        _logger.info(f"Generated domain: {domain}")
        return {'model': model_name, 'domain': domain}

    def process_input(self):
        try:
            # Step 1: Discover the model name
            model_name = self.discover_model_name(self.user_input)
            if not model_name:
                raise ValueError("Unable to identify the model from the query.")

            # Step 2: Generate the domain filter using the discovered model name
            llm_response = self.generate_domain_filter(self.user_input, model_name)
            
            domain_filter = llm_response.get('domain')
            
            if domain_filter is None:
                raise ValueError(f"Invalid response format: {llm_response}")
            
            model = self.env[model_name]
            records = model.search(domain_filter)
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'Query Results ({len(records)} records)',
                'res_model': model_name,
                'view_mode': 'list,form',
                'domain': domain_filter,
                'target': 'current',
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }