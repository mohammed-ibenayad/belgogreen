from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class MailMessage(models.Model):
    _inherit = 'mail.message'
    
    ai_suggest_ids = fields.One2many(
        'ai.odoo.suggest', 
        'message_id', 
        string='AI Suggestions'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to detect audio messages"""
        messages = super(MailMessage, self).create(vals_list)
        
        for message in messages:
            # Check if this is an audio message in a channel
            if (message.model == 'discuss.channel' and 
                message.attachment_ids and 
                any(att.mimetype and 'audio' in att.mimetype for att in message.attachment_ids)):
                
                try:
                    # Create AI suggestion for audio processing
                    self.env['ai.odoo.suggest'].sudo().process_audio_message(message.id)
                except Exception as e:
                    _logger.error(f"Error processing audio message: {str(e)}")
        
        return messages