from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class DynamicQueryReport(models.TransientModel):
    _name = 'dynamic.query.report'
    _description = 'Dynamic Query Report'

    user_input = fields.Text(string="Enter your query")

    def send_to_llm(self, user_input):
        # Replace with your LLM API endpoint and key
        llm_api_url = "https://api.llmprovider.com/generate"
        headers = {
            "Authorization": "Bearer YOUR_LLM_API_KEY",
            "Content-Type": "application/json"
        }
        data = {
            "prompt": f"Convert the following user request into an Odoo model name and domain filter. Return the response in JSON format with keys 'model' and 'domain': {user_input}",
            "max_tokens": 100
        }
        response = requests.post(llm_api_url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json().get("output")
        else:
            raise Exception("Failed to generate query from LLM")

    def process_input(self):
        # Step 1: Send user input to LLM
        llm_response = self.send_to_llm(self.user_input)
        _logger.info(f"Generated response from LLM: {llm_response}")

        try:
            # Parse the LLM response (expected format: {"model": "sale.order", "domain": [...]})
            model_name = llm_response.get("model")
            domain_filter = llm_response.get("domain")

            if not model_name or not domain_filter:
                raise ValueError("Invalid LLM response: Missing model or domain")

            # Step 2: Execute the query in Odoo
            model = self.env[model_name]
            records = model.search(domain_filter)
        except Exception as e:
            _logger.error(f"Error executing query: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f"Invalid query: {str(e)}",
                    'type': 'danger',
                    'sticky': False,
                }
            }

        # Step 3: Return results in a tree view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Query Results',
            'res_model': model_name,
            'view_mode': 'tree,form',
            'domain': domain_filter,
        }