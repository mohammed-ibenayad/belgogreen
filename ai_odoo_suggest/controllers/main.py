from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class AISuggestController(http.Controller):
    
    @http.route('/ai_odoo_suggest/confirm', type='json', auth='user')
    def confirm_action(self, suggestion_id, action_index):
        """Confirm and execute an AI suggested action"""
        try:
            suggestion = request.env['ai.odoo.suggest'].browse(suggestion_id)
            if not suggestion.exists():
                return {'success': False, 'message': 'Suggestion not found'}
            
            result = suggestion.confirm_action(action_index)
            return result
        except Exception as e:
            _logger.error(f"Error confirming action: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    @http.route('/ai_odoo_suggest/reject', type='json', auth='user')
    def reject_action(self, suggestion_id, action_index):
        """Reject an AI suggested action"""
        try:
            suggestion = request.env['ai.odoo.suggest'].browse(suggestion_id)
            if not suggestion.exists():
                return {'success': False, 'message': 'Suggestion not found'}
            
            result = suggestion.reject_action(action_index)
            return result
        except Exception as e:
            _logger.error(f"Error rejecting action: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    @http.route('/ai_odoo_suggest/confirm_link', type='http', auth='user', website=True, csrf=False)
    def confirm_action_link(self, suggestion_id, action_index, **kwargs):
        """Confirm action via link"""
        try:
            suggestion_id = int(suggestion_id)
            action_index = int(action_index)
            
            suggestion = request.env['ai.odoo.suggest'].browse(suggestion_id)
            if not suggestion.exists():
                return request.render('ai_odoo_suggest.action_result', {
                    'success': False,
                    'message': 'Suggestion not found',
                    'title': 'Error',
                    'channel_id': None
                })
            
            result = suggestion.confirm_action(action_index)
            
            return request.render('ai_odoo_suggest.action_result', {
                'success': result.get('success', True),
                'message': result.get('result', {}).get('message', 'Action confirmed successfully!'),
                'title': 'Action Confirmed',
                'channel_id': suggestion.channel_id.id if suggestion.channel_id else None
            })
        except Exception as e:
            _logger.error(f"Error confirming action via link: {str(e)}", exc_info=True)
            return request.render('ai_odoo_suggest.action_result', {
                'success': False,
                'message': str(e),
                'title': 'Error',
                'channel_id': None
            })
    
    @http.route('/ai_odoo_suggest/reject_link', type='http', auth='user', website=True, csrf=False)
    def reject_action_link(self, suggestion_id, action_index, **kwargs):
        """Reject action via link"""
        try:
            suggestion_id = int(suggestion_id)
            action_index = int(action_index)
            
            suggestion = request.env['ai.odoo.suggest'].browse(suggestion_id)
            if not suggestion.exists():
                return request.render('ai_odoo_suggest.action_result', {
                    'success': False,
                    'message': 'Suggestion not found',
                    'title': 'Error',
                    'channel_id': None
                })
            
            result = suggestion.reject_action(action_index)
            
            return request.render('ai_odoo_suggest.action_result', {
                'success': result.get('success', True),
                'message': result.get('message', 'Action rejected successfully'),
                'title': 'Action Rejected',
                'channel_id': suggestion.channel_id.id if suggestion.channel_id else None
            })
        except Exception as e:
            _logger.error(f"Error rejecting action via link: {str(e)}", exc_info=True)
            return request.render('ai_odoo_suggest.action_result', {
                'success': False,
                'message': str(e),
                'title': 'Error',
                'channel_id': None
            })