from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import base64
import io
import tempfile
import openai
import os
from datetime import datetime

_logger = logging.getLogger(__name__)

class AIOdooSuggest(models.Model):
    _name = 'ai.odoo.suggest'
    _description = 'AI Odoo Suggestions'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Add this line
    _order = 'create_date desc'

    name = fields.Char('Title', required=True, tracking=True)  # Add tracking=True
    message_id = fields.Many2one('mail.message', 'Original Message', required=True, ondelete='cascade')
    audio_file = fields.Binary('Audio File', attachment=True)
    audio_filename = fields.Char('Audio Filename')
    transcription = fields.Text('Transcription', tracking=True)  # Add tracking=True
    ai_response = fields.Text('AI Response', tracking=True)  # Add tracking=True
    suggested_actions = fields.Text('Suggested Actions', help='JSON format of suggested actions')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('transcribed', 'Transcribed'),
        ('processed', 'Processed'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('executed', 'Executed'),
    ], default='pending', required=True, tracking=True)  # Add tracking=True
    executed_actions = fields.Text('Executed Actions')
    user_id = fields.Many2one('res.users', 'User', compute='_compute_user_id', store=True)
    channel_id = fields.Many2one('discuss.channel', 'Channel', compute='_compute_channel_id', store=True)

    @api.depends('message_id.author_id')
    def _compute_user_id(self):
        for record in self:
            if record.message_id and record.message_id.author_id:
                # Get the user associated with the partner
                user = self.env['res.users'].search([('partner_id', '=', record.message_id.author_id.id)], limit=1)
                record.user_id = user.id if user else False
            else:
                record.user_id = False

    @api.depends('message_id.model', 'message_id.res_id')
    def _compute_channel_id(self):
        for record in self:
            if record.message_id and record.message_id.model == 'discuss.channel':
                record.channel_id = record.message_id.res_id
            else:
                record.channel_id = False

    def action_process(self):
        """Manual process button"""
        self.ensure_one()
        if self.status == 'pending':
            self._transcribe_audio()
        return True

    @api.model
    def process_audio_message(self, message_id):
        """Process an audio message and generate suggestions"""
        message = self.env['mail.message'].browse(message_id)
        if not message.exists() or not message.attachment_ids:
            _logger.warning(f"No audio attachment found for message {message_id}")
            return False
        
        # Find audio attachment
        audio_attachment = message.attachment_ids.filtered(
            lambda a: a.mimetype and 'audio' in a.mimetype
        )
        
        if not audio_attachment:
            _logger.warning(f"No audio file found in message {message_id}")
            return False
        
        # Take the first audio attachment
        audio_attachment = audio_attachment[0]
        
        # Create AI suggestion record
        ai_suggest = self.create({
            'name': f'AI Suggestion - {message.subject or message.preview or "Audio Message"}',
            'message_id': message_id,
            'audio_file': audio_attachment.datas,
            'audio_filename': audio_attachment.name,
        })
        
        # Process the audio asynchronously
        try:
            ai_suggest._transcribe_audio()
        except Exception as e:
            _logger.error(f"Error in audio processing: {str(e)}")
            
        return ai_suggest

    def _transcribe_audio(self):
        """Transcribe audio file using OpenAI Whisper"""
        import os
        self.ensure_one()
        
        if not self.audio_file:
            return
            
        audio_data = base64.b64decode(self.audio_file)
        
        # Determine file extension from filename or default to mp3
        file_ext = '.mp3'
        if self.audio_filename:
            _, ext = os.path.splitext(self.audio_filename)
            if ext:
                file_ext = ext
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            # Try direct transcription (works for mp3, webm, m4a, etc.)
            transcription = self._call_whisper_api(temp_file_path)
            self.transcription = transcription
            self.status = 'transcribed'
            self._process_with_ai_agent()
            
        except Exception as e:
            _logger.error(f"Error transcribing audio ({file_ext}): {str(e)}")
            self.transcription = f"Error transcribing audio: {str(e)}"
            self.status = 'pending'
        finally:
            import os
            try:
                os.unlink(temp_file_path)
            except:
                pass

    def _call_whisper_api(self, audio_file_path):
        """Call OpenAI Whisper API for transcription"""
        try:
            api_key = self.env['ir.config_parameter'].sudo().get_param('ai_odoo_suggest.openai_api_key')
            if not api_key:
                raise UserError(_("OpenAI API key not configured"))
            
            # Use the new OpenAI client (v1.0+)
            client = openai.OpenAI(api_key=api_key)
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            
            return transcript.text
        except Exception as e:
            _logger.error(f"Whisper API error: {str(e)}")
            return f"Transcription failed: {str(e)}"

    def _process_with_ai_agent(self):
        """Process transcription with AI agent"""
        self.ensure_one()
        
        if not self.transcription:
            return
        
        try:
            # Prepare the AI prompt
            prompt = self._prepare_ai_prompt(self.transcription)
            
            # Call AI agent
            response = self._call_openai_agent(prompt)
            
            # Parse AI response for actions
            actions = self._parse_ai_response(response)
            
            self.ai_response = response
            self.suggested_actions = json.dumps(actions, ensure_ascii=False)
            self.status = 'processed'
            
            # Create suggestion messages in the channel
            if self.channel_id:
                self._create_suggestion_messages(actions)
            
        except Exception as e:
            _logger.error(f"AI agent processing error: {str(e)}")
            self.ai_response = f"AI processing failed: {str(e)}"

    def _prepare_ai_prompt(self, transcription):
        """Prepare prompt for AI agent"""
        return f"""
You are an AI assistant that helps users interact with Odoo ERP system through voice commands.
The user said: "{transcription}"

Please analyze this request and provide a structured response with suggested actions in Odoo.
Each action should include:
1. Action type (create, update, delete, search, etc.)
2. Model name (res.partner, sale.order, etc.)
3. Field values or search criteria
4. A human-readable description of what will happen

Return ONLY a valid JSON array of action objects, nothing else.

Example response format:
[
    {{
        "action": "create",
        "model": "res.partner",
        "values": {{"name": "John Doe", "email": "john@example.com"}},
        "description": "Create a new customer named John Doe"
    }},
    {{
        "action": "search",
        "model": "sale.order",
        "domain": [["name", "ilike", "SO001"]],
        "description": "Search for sales order containing SO001"
    }}
]
"""

    def _call_openai_agent(self, prompt):
        """Call OpenAI GPT for processing"""
        try:
            api_key = self.env['ir.config_parameter'].sudo().get_param('ai_odoo_suggest.openai_api_key')
            if not api_key:
                raise UserError(_("OpenAI API key not configured"))
            
            # Use the new OpenAI client (v1.0+)
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model="gpt-4",  # or "gpt-3.5-turbo"
                messages=[
                    {"role": "system", "content": "You are an AI assistant that helps users interact with Odoo ERP system. Respond with structured JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content
        except Exception as e:
            _logger.error(f"OpenAI agent error: {str(e)}")
            raise UserError(f"AI processing failed: {str(e)}")

    def _parse_ai_response(self, response):
        """Parse AI response and extract actions"""
        try:
            # Extract JSON from response if wrapped in markdown
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()
            
            # Clean up the response
            json_str = json_str.strip()
            
            parsed = json.loads(json_str)
            
            # Ensure it's a list
            if isinstance(parsed, dict):
                parsed = [parsed]
            
            return parsed
        except Exception as e:
            _logger.error(f"Error parsing AI response: {str(e)}\nResponse was: {response}")
            return []

    def _create_suggestion_messages(self, actions):
        """Create suggestion messages in the channel"""
        self.ensure_one()
        
        if not self.channel_id or not actions:
            return
        
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        for i, action in enumerate(actions):
            description = action.get('description', 'No description')
            model = action.get('model', '')
            action_type = action.get('action', '').upper()
            
            # Create URLs for confirm and reject
            confirm_url = f"{base_url}/ai_odoo_suggest/confirm_link?suggestion_id={self.id}&action_index={i}"
            reject_url = f"{base_url}/ai_odoo_suggest/reject_link?suggestion_id={self.id}&action_index={i}"
            
            body = f"""
    <div style="border-left: 4px solid #17a2b8; padding: 15px; margin: 10px 0; background-color: #f8f9fa; border-radius: 5px;">
        <h5 style="color: #17a2b8; margin-bottom: 10px;">
            <span style="font-size: 1.2em;">🤖</span> AI Suggestion #{i+1}
        </h5>
        <p style="margin: 5px 0;"><strong>Action:</strong> {description}</p>
        <p style="margin: 5px 0;"><strong>Model:</strong> <code>{model}</code></p>
        <p style="margin: 5px 0;"><strong>Operation:</strong> <span style="background-color: #007bff; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.85em;">{action_type}</span></p>
        <hr style="margin: 10px 0;"/>
        <div style="margin-top: 10px;">
            <a href="{confirm_url}" 
               style="display: inline-block; background-color: #28a745; color: white; text-decoration: none; padding: 8px 15px; border-radius: 4px; margin-right: 5px; font-size: 14px;"
               target="_blank">
                ✓ Confirm Action
            </a>
            <a href="{reject_url}" 
               style="display: inline-block; background-color: #dc3545; color: white; text-decoration: none; padding: 8px 15px; border-radius: 4px; font-size: 14px;"
               target="_blank">
                ✗ Reject Action
            </a>
        </div>
        <p style="margin-top: 10px; font-size: 0.85em; color: #6c757d;">
            💡 Click the links above to confirm or reject this suggestion
        </p>
    </div>
    """
            
            self.env['mail.message'].sudo().create({
                'model': 'discuss.channel',
                'res_id': self.channel_id.id,
                'body': body,
                'message_type': 'notification',
                'author_id': self.env.user.partner_id.id,
            })

    def confirm_action(self, action_index):
        """Confirm and execute a specific action"""
        self.ensure_one()
        
        if self.status in ['confirmed', 'executed']:
            return {'success': False, 'message': 'Action already processed'}
        
        actions = json.loads(self.suggested_actions or '[]')
        if action_index >= len(actions):
            raise UserError(_("Invalid action index"))
        
        action = actions[action_index]
        
        try:
            # Execute the action
            result = self._execute_action(action)
            
            # Update executed actions
            executed_actions = json.loads(self.executed_actions or '[]')
            executed_actions.append({
                'action': action,
                'result': result,
                'executed_at': fields.Datetime.now().isoformat(),
                'executed_by': self.env.user.id
            })
            
            self.executed_actions = json.dumps(executed_actions, ensure_ascii=False)
            
            # Update status
            if len(executed_actions) >= len(actions):
                self.status = 'executed'
            else:
                self.status = 'confirmed'
            
            # Send confirmation message
            if self.channel_id:
                self._send_confirmation_message(action, result)
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            _logger.error(f"Error executing action: {str(e)}")
            raise UserError(f"Error executing action: {str(e)}")

    def _execute_action(self, action):
        """Execute a single action in Odoo"""
        action_type = action.get('action', '').lower()
        model_name = action.get('model', '')
        
        if not model_name or not action_type:
            raise UserError(_("Invalid action configuration"))
        
        # Check if model exists
        if model_name not in self.env:
            raise UserError(_(f"Model {model_name} does not exist"))
        
        model = self.env[model_name].sudo()
        
        if action_type == 'create':
            values = action.get('values', {})
            record = model.create(values)
            return {
                'created_id': record.id,
                'message': f'Created {model_name} with ID {record.id}',
                'display_name': record.display_name if hasattr(record, 'display_name') else str(record.id)
            }
        
        elif action_type in ['update', 'write']:
            domain = action.get('domain', [])
            values = action.get('values', {})
            records = model.search(domain)
            if records:
                records.write(values)
                return {
                    'updated_count': len(records),
                    'message': f'Updated {len(records)} {model_name} record(s)'
                }
            else:
                return {
                    'updated_count': 0,
                    'message': 'No records found matching the criteria'
                }
        
        elif action_type == 'delete':
            domain = action.get('domain', [])
            records = model.search(domain)
            count = len(records)
            if records:
                records.unlink()
                return {
                    'deleted_count': count,
                    'message': f'Deleted {count} {model_name} record(s)'
                }
            else:
                return {
                    'deleted_count': 0,
                    'message': 'No records found matching the criteria'
                }
        
        elif action_type == 'search':
            domain = action.get('domain', [])
            limit = action.get('limit', 10)
            records = model.search(domain, limit=limit)
            return {
                'found_count': len(records),
                'records': [{'id': r.id, 'display_name': r.display_name} for r in records[:5]],
                'message': f'Found {len(records)} {model_name} record(s)'
            }
        
        else:
            raise UserError(f"Unsupported action type: {action_type}")

    def _send_confirmation_message(self, action, result):
        """Send confirmation message to the channel"""
        self.ensure_one()
        
        if not self.channel_id:
            return
        
        body = f"""
<div class="alert alert-success">
    <h5>✅ Action Executed Successfully</h5>
    <p><strong>Action:</strong> {action.get('description', '')}</p>
    <p><strong>Result:</strong> {result.get('message', 'Action completed')}</p>
</div>
"""
        
        self.env['mail.message'].sudo().create({
            'model': 'discuss.channel',
            'res_id': self.channel_id.id,
            'body': body,
            'message_type': 'notification',
            'author_id': self.env.user.partner_id.id,
        })

    def reject_action(self, action_index):
        """Reject a specific action"""
        self.ensure_one()
        
        actions = json.loads(self.suggested_actions or '[]')
        if action_index >= len(actions):
            raise UserError(_("Invalid action index"))
        
        action = actions[action_index]
        self.status = 'rejected'
        
        # Send rejection message
        if self.channel_id:
            body = f"""
<div class="alert alert-warning">
    <h5>❌ Action Rejected</h5>
    <p><strong>Action:</strong> {action.get('description', '')}</p>
</div>
"""
            
            self.env['mail.message'].sudo().create({
                'model': 'discuss.channel',
                'res_id': self.channel_id.id,
                'body': body,
                'message_type': 'notification',
                'author_id': self.env.user.partner_id.id,
            })
        
        return {'success': True, 'message': 'Action rejected'}