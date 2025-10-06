from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import requests
import logging
import base64
from pydub import AudioSegment
import io
import tempfile
import openai
from datetime import datetime

_logger = logging.getLogger(__name__)

class AIOdooSuggest(models.Model):
    _name = 'ai.odoo.suggest'
    _description = 'AI Odoo Suggestions'
    _order = 'create_date desc'

    name = fields.Char('Title', required=True)
    message_id = fields.Many2one('mail.message', 'Original Message', required=True)
    audio_file = fields.Binary('Audio File', attachment=True)
    audio_filename = fields.Char('Audio Filename')
    transcription = fields.Text('Transcription')
    ai_response = fields.Text('AI Response')
    suggested_actions = fields.Text('Suggested Actions', help='JSON format of suggested actions')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('transcribed', 'Transcribed'),
        ('processed', 'Processed'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('executed', 'Executed'),
    ], default='pending', tracking=True)
    executed_actions = fields.Text('Executed Actions')
    user_id = fields.Many2one('res.users', 'User', compute='_compute_user_id', store=True)
    channel_id = fields.Many2one('mail.channel', 'Channel', compute='_compute_channel_id', store=True)

    @api.depends('message_id.author_id')
    def _compute_user_id(self):
        for record in self:
            record.user_id = record.message_id.author_id

    @api.depends('message_id.channel_ids')
    def _compute_channel_id(self):
        for record in self:
            record.channel_id = record.message_id.channel_ids[:1]

    @api.model
    def process_audio_message(self, message_id):
        """Process an audio message and generate suggestions"""
        message = self.env['mail.message'].browse(message_id)
        if not message or not message.attachment_ids:
            raise UserError(_("No audio attachment found"))
        
        # Find audio attachment
        audio_attachment = message.attachment_ids.filtered(
            lambda a: a.mimetype and 'audio' in a.mimetype
        )
        
        if not audio_attachment:
            raise UserError(_("No audio file found in message"))
        
        # Create AI suggestion record
        ai_suggest = self.create({
            'name': f'AI Suggestion - {message.subject or "Audio Message"}',
            'message_id': message_id,
            'audio_file': audio_attachment.datas,
            'audio_filename': audio_attachment.name,
        })
        
        # Process the audio
        ai_suggest._transcribe_audio()
        return ai_suggest

    def _transcribe_audio(self):
        """Transcribe audio file using OpenAI Whisper or similar"""
        for record in self:
            if not record.audio_file:
                continue
                
            # Decode the audio file
            audio_data = base64.b64decode(record.audio_file)
            
            # Convert to proper format for transcription
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Convert audio to proper format if needed
                audio = AudioSegment.from_file(temp_file_path)
                audio.export(temp_file_path, format="mp3")
                
                # Transcribe using OpenAI Whisper
                transcription = self._call_whisper_api(temp_file_path)
                record.transcription = transcription
                record.status = 'transcribed'
                
                # Process transcription with AI agent
                record._process_with_ai_agent()
                
            except Exception as e:
                _logger.error(f"Error transcribing audio: {str(e)}")
                record.transcription = f"Error transcribing audio: {str(e)}"
                record.status = 'pending'
            finally:
                import os
                os.unlink(temp_file_path)

    def _call_whisper_api(self, audio_file_path):
        """Call OpenAI Whisper API for transcription"""
        try:
            openai.api_key = self.env['ir.config_parameter'].sudo().get_param('ai_odoo_suggest.openai_api_key')
            if not openai.api_key:
                raise UserError(_("OpenAI API key not configured"))
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)
            
            return transcript.text
        except Exception as e:
            _logger.error(f"Whisper API error: {str(e)}")
            return "Transcription failed: " + str(e)

    def _process_with_ai_agent(self):
        """Process transcription with AI agent (OpenAI/DeepSeek)"""
        for record in self:
            if not record.transcription:
                continue
            
            try:
                # Prepare the AI prompt
                prompt = self._prepare_ai_prompt(record.transcription)
                
                # Call AI agent (OpenAI GPT)
                response = self._call_openai_agent(prompt)
                
                # Parse AI response for actions
                actions = self._parse_ai_response(response)
                
                record.ai_response = response
                record.suggested_actions = json.dumps(actions)
                record.status = 'processed'
                
                # Create suggestion messages in the channel
                self._create_suggestion_messages(record, actions)
                
            except Exception as e:
                _logger.error(f"AI agent processing error: {str(e)}")
                record.ai_response = f"AI processing failed: {str(e)}"
                record.status = 'pending'

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
        5. The actual Odoo method call that would be executed
        
        Return the response as a JSON array of action objects.
        
        Example response format:
        [
            {{
                "action": "create",
                "model": "res.partner",
                "values": {{"name": "John Doe", "email": "john@example.com"}},
                "description": "Create a new customer named John Doe",
                "odoo_call": "self.env['res.partner'].create({{'name': 'John Doe', 'email': 'john@example.com'}})"
            }},
            {{
                "action": "update",
                "model": "sale.order",
                "domain": [["name", "=", "SO001"]],
                "values": {{"state": "confirmed"}},
                "description": "Confirm the sales order SO001",
                "odoo_call": "orders = self.env['sale.order'].search([('name', '=', 'SO001')]); orders.write({{'state': 'confirmed'}})"
            }}
        ]
        """

    def _call_openai_agent(self, prompt):
        """Call OpenAI GPT for processing"""
        try:
            openai.api_key = self.env['ir.config_parameter'].sudo().get_param('ai_odoo_suggest.openai_api_key')
            if not openai.api_key:
                raise UserError(_("OpenAI API key not configured"))
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an AI assistant that helps users interact with Odoo ERP system. Respond with structured JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content
        except Exception as e:
            _logger.error(f"OpenAI agent error: {str(e)}")
            return f"AI processing failed: {str(e)}"

    def _parse_ai_response(self, response):
        """Parse AI response and extract actions"""
        try:
            # Extract JSON from response if wrapped in markdown
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()
            
            # Clean up the response to extract JSON
            if json_str.startswith('```'):
                json_str = json_str[3:]
            if json_str.endswith('```'):
                json_str = json_str[:-3]
            
            return json.loads(json_str)
        except Exception as e:
            _logger.error(f"Error parsing AI response: {str(e)}")
            return []

    def _create_suggestion_messages(self, record, actions):
        """Create suggestion messages in the channel"""
        for i, action in enumerate(actions):
            body = f"""
            <div class="ai-suggestion">
                <h4>AI Suggestion #{i+1}</h4>
                <p><strong>Action:</strong> {action.get('description', 'No description')}</p>
                <p><strong>Model:</strong> {action.get('model', '')}</p>
                <p><strong>Operation:</strong> {action.get('action', '').upper()}</p>
                
                <div class="suggestion-actions">
                    <button class="btn btn-success btn-sm ai-confirm" 
                            data-suggestion-id="{record.id}" 
                            data-action-index="{i}">Confirm</button>
                    <button class="btn btn-danger btn-sm ai-reject" 
                            data-suggestion-id="{record.id}" 
                            data-action-index="{i}">Reject</button>
                </div>
            </div>
            """
            
            self.env['mail.message'].create({
                'model': 'mail.channel',
                'res_id': record.channel_id.id,
                'body': body,
                'message_type': 'comment',
                'subtype_id': self.env.ref('mail.mt_comment').id,
                'author_id': self.env.user.partner_id.id,
            })

    def confirm_action(self, action_index):
        """Confirm and execute a specific action"""
        for record in self:
            if record.status in ['confirmed', 'executed']:
                continue
            
            actions = json.loads(record.suggested_actions or '[]')
            if action_index >= len(actions):
                raise UserError(_("Invalid action index"))
            
            action = actions[action_index]
            
            try:
                # Execute the action
                result = self._execute_action(action)
                
                # Update status
                executed_actions = json.loads(record.executed_actions or '[]')
                executed_actions.append({
                    'action': action,
                    'result': result,
                    'executed_at': fields.Datetime.now(),
                    'executed_by': self.env.user.id
                })
                
                record.executed_actions = json.dumps(executed_actions)
                
                # Update status if all actions are confirmed
                if len(executed_actions) == len(actions):
                    record.status = 'executed'
                else:
                    record.status = 'confirmed'
                
                # Send confirmation message
                self._send_confirmation_message(record, action, result)
                
            except Exception as e:
                _logger.error(f"Error executing action: {str(e)}")
                raise UserError(f"Error executing action: {str(e)}")

    def _execute_action(self, action):
        """Execute a single action in Odoo"""
        action_type = action.get('action', '').lower()
        model_name = action.get('model', '')
        
        if not model_name or not action_type:
            raise UserError(_("Invalid action configuration"))
        
        model = self.env[model_name]
        
        if action_type == 'create':
            values = action.get('values', {})
            record = model.create(values)
            return {'created_id': record.id, 'message': f'Created {model_name} with ID {record.id}'}
        
        elif action_type == 'update':
            domain = action.get('domain', [])
            values = action.get('values', {})
            records = model.search(domain)
            if records:
                records.write(values)
                return {'updated_count': len(records), 'message': f'Updated {len(records)} {model_name} records'}
            else:
                raise UserError(_("No records found matching the criteria"))
        
        elif action_type == 'delete':
            domain = action.get('domain', [])
            records = model.search(domain)
            if records:
                records.unlink()
                return {'deleted_count': len(records), 'message': f'Deleted {len(records)} {model_name} records'}
            else:
                raise UserError(_("No records found matching the criteria"))
        
        elif action_type == 'search':
            domain = action.get('domain', [])
            records = model.search(domain)
            return {'found_count': len(records), 'message': f'Found {len(records)} {model_name} records'}
        
        else:
            raise UserError(f"Unsupported action type: {action_type}")

    def _send_confirmation_message(self, record, action, result):
        """Send confirmation message to the channel"""
        body = f"""
        <div class="ai-confirmation">
            <p><strong>✅ Action Confirmed:</strong></p>
            <p>{action.get('description', '')}</p>
            <p><strong>Result:</strong> {result.get('message', 'Action completed')}</p>
        </div>
        """
        
        self.env['mail.message'].create({
            'model': 'mail.channel',
            'res_id': record.channel_id.id,
            'body': body,
            'message_type': 'comment',
            'subtype_id': self.env.ref('mail.mt_comment').id,
            'author_id': self.env.user.partner_id.id,
        })

    def reject_action(self, action_index):
        """Reject a specific action"""
        for record in self:
            actions = json.loads(record.suggested_actions or '[]')
            if action_index >= len(actions):
                raise UserError(_("Invalid action index"))
            
            action = actions[action_index]
            
            # Send rejection message
            body = f"""
            <div class="ai-rejection">
                <p><strong>❌ Action Rejected:</strong></p>
                <p>{action.get('description', '')}</p>
                <p><strong>Reason:</strong> User rejected this suggestion</p>
            </div>
            """
            
            self.env['mail.message'].create({
                'model': 'mail.channel',
                'res_id': record.channel_id.id,
                'body': body,
                'message_type': 'comment',
                'subtype_id': self.env.ref('mail.mt_comment').id,
                'author_id': self.env.user.partner_id.id,
            })