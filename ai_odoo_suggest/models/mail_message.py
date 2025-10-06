from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class MailMessage(models.Model):
    _inherit = 'mail.message'

    ai_suggest_ids = fields.One2many('ai.odoo.suggest', 'message_id', string='AI Suggestions')

    @api.model
    def create(self, vals):
        """Override create to detect audio messages"""
        message = super(MailMessage, self).create(vals)
        
        # Check if this is an audio message in a channel
        if (message.model == 'mail.channel' and 
            message.attachment_ids and 
            any('audio' in att.mimetype for att in message.attachment_ids)):
            
            try:
                # Create AI suggestion for audio processing
                ai_suggest_model = self.env['ai.odoo.suggest']
                ai_suggest_model.process_audio_message(message.id)
            except Exception as e:
                _logger.error(f"Error processing audio message: {str(e)}")
        
        return message