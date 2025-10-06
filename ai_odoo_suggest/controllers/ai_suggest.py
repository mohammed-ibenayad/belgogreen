from odoo import http
from odoo.http import request
import json

class AIOdooSuggestController(http.Controller):
    
    @http.route('/ai_suggest/confirm_action', type='json', auth='user')
    def confirm_action(self, **kwargs):
        """Confirm an AI suggested action"""
        suggestion_id = kwargs.get('suggestion_id')
        action_index = kwargs.get('action_index')
        
        suggestion = request.env['ai.odoo.suggest'].browse(int(suggestion_id))
        if suggestion:
            suggestion.confirm_action(int(action_index))
            return {'status': 'success', 'message': 'Action confirmed and executed'}
        return {'status': 'error', 'message': 'Suggestion not found'}

    @http.route('/ai_suggest/reject_action', type='json', auth='user')
    def reject_action(self, **kwargs):
        """Reject an AI suggested action"""
        suggestion_id = kwargs.get('suggestion_id')
        action_index = kwargs.get('action_index')
        
        suggestion = request.env['ai.odoo.suggest'].browse(int(suggestion_id))
        if suggestion:
            suggestion.reject_action(int(action_index))
            return {'status': 'success', 'message': 'Action rejected'}
        return {'status': 'error', 'message': 'Suggestion not found'}