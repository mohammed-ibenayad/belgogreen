# -*- coding: utf-8 -*-

import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Appointment reference constants for automation rules
ALL_APPOINTMENT_REFS = ['APT-ENERG-CNT', 'APT-ENERG-COM', 'APT-NISOL-CNT', 'APT-NISOL-COM']
CALL_CENTER_APPOINTMENT_REFS = ['APT-ENERG-CNT', 'APT-NISOL-CNT']


class AppointmentAnswerInput(models.Model):
    _inherit = 'appointment.answer.input'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger automation rules on new appointment answers"""
        records = super(AppointmentAnswerInput, self).create(vals_list)

        for record in records:
            self._process_appointment_answer(record)

        return records

    def write(self, vals):
        """Override write to trigger automation rules on updates"""
        result = super(AppointmentAnswerInput, self).write(vals)

        # Only process if this is a new record (create_date == write_date)
        for record in self:
            if record.create_date == record.write_date:
                self._process_appointment_answer(record)

        return result

    def _process_appointment_answer(self, record):
        """Process all automation rules for appointment answers"""
        self._add_conjoint_as_contact(record)
        self._update_contact_info(record)
        self._update_appointment_title(record)
        self._set_partner_on_behalf(record)

    def _add_conjoint_as_contact(self, record):
        """
        Add conjoint as Contact - Automation Rule
        Creates or updates spouse contact records based on appointment answers
        Only applies to appointment types: APT-ENERG-CNT, APT-ENERG-COM, APT-NISOL-CNT, APT-NISOL-COM
        """
        try:
            # Check appointment type restriction
            if not (record.calendar_event_id and record.calendar_event_id.appointment_type_id):
                return

            if not record.calendar_event_id.appointment_type_id.x_appointment_ref:
                return

            if record.calendar_event_id.appointment_type_id.x_appointment_ref not in ALL_APPOINTMENT_REFS:
                return

            if not record.partner_id:
                return

            spouse_data = {}

            # Check if this is the spouse name question
            if record.question_id.display_name == 'Nom du conjoint' and record.value_text_box:
                spouse_data['name'] = record.value_text_box
                _logger.info("Processing spouse name: %s for partner ID %s",
                           record.value_text_box, record.partner_id.id)

            # Check if this is the spouse phone number question
            elif record.question_id.display_name == 'Numéro de téléphone du conjoint' and record.value_text_box:
                spouse_data['phone'] = record.value_text_box
                _logger.info("Processing spouse phone: %s for partner ID %s",
                           record.value_text_box, record.partner_id.id)

            if spouse_data:
                # Check if a spouse already exists
                domain = [('parent_id', '=', record.partner_id.id)]
                if 'name' in spouse_data:
                    domain.append(('name', '=', spouse_data['name']))

                existing_spouse = self.env['res.partner'].search(domain, limit=1)

                if existing_spouse:
                    # Update existing spouse record if needed
                    if 'phone' in spouse_data and existing_spouse.phone != spouse_data['phone']:
                        existing_spouse.write({'phone': spouse_data['phone']})
                        _logger.info("Updated existing spouse (ID %s) phone to: %s",
                                   existing_spouse.id, spouse_data['phone'])
                    else:
                        _logger.info("Spouse already exists (ID %s), no update needed",
                                   existing_spouse.id)

                elif 'name' in spouse_data:
                    # Create new spouse contact with all available information
                    create_vals = {
                        'name': spouse_data['name'],
                        'parent_id': record.partner_id.id,
                        'is_company': False
                    }
                    if 'phone' in spouse_data:
                        create_vals['phone'] = spouse_data['phone']

                    spouse = self.env['res.partner'].with_context(
                        mail_create_nosubscribe=True,
                        tracking_disable=True
                    ).create(create_vals)
                    _logger.info("Created new spouse contact (ID %s) '%s' for partner ID %s",
                               spouse.id, spouse.name, record.partner_id.id)

        except Exception as e:
            _logger.error("Add Conjoint as Contact - Error processing record ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _update_contact_info(self, record):
        """
        Update Contact Info - Automation Rule
        Updates partner contact information (address, postal code, city, country) from appointment answers
        Only applies to appointment types: APT-ENERG-CNT, APT-ENERG-COM, APT-NISOL-CNT, APT-NISOL-COM
        """
        try:
            # Check appointment type restriction
            if not (record.calendar_event_id and record.calendar_event_id.appointment_type_id):
                return

            if not record.calendar_event_id.appointment_type_id.x_appointment_ref:
                return

            if record.calendar_event_id.appointment_type_id.x_appointment_ref not in ALL_APPOINTMENT_REFS:
                return

            if not record.partner_id:
                return

            update_values = {}

            # Map questions to partner fields
            if record.question_id.display_name == 'Adresse':
                update_values['street'] = record.value_text_box
                _logger.info("Updating street for partner ID %s: %s",
                           record.partner_id.id, record.value_text_box)

            elif record.question_id.display_name == 'Code Postale':
                update_values['zip'] = record.value_text_box
                _logger.info("Updating zip code for partner ID %s: %s",
                           record.partner_id.id, record.value_text_box)

            elif record.question_id.display_name == 'Ville':
                update_values['city'] = record.value_text_box
                _logger.info("Updating city for partner ID %s: %s",
                           record.partner_id.id, record.value_text_box)

            elif record.question_id.display_name == 'Pays' and record.value_answer_id:
                # For selection field, use value_answer_id instead of value_text_box
                country_name = record.value_answer_id.name.strip()
                _logger.info("Processing country for partner ID %s: '%s'",
                           record.partner_id.id, country_name)

                country = self.env['res.country'].search([('name', '=ilike', country_name)], limit=1)

                if country:
                    update_values['country_id'] = country.id
                    _logger.info("Country matched: %s (ID: %s)", country.name, country.id)
                else:
                    _logger.warning("No country found for name: '%s' (Partner ID: %s)",
                                  country_name, record.partner_id.id)

            # Update the contact if we have any values
            if update_values:
                _logger.info("Updating partner %s with fields: %s",
                           record.partner_id.id, list(update_values.keys()))
                record.partner_id.with_context(mail_create_nosubscribe=True).write(update_values)

        except Exception as e:
            _logger.error("Update Contact Info - Error processing record ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _update_appointment_title(self, record):
        """
        Update Appointment Title - Automation Rule
        Builds appointment title from various appointment answer fields
        Format: [SMS Icon]/Client Name/Postal Code/Phone/Need/Seller
        Only applies to appointment types: APT-ENERG-CNT, APT-ENERG-COM, APT-NISOL-CNT, APT-NISOL-COM
        """
        try:
            if not (record.partner_id and record.calendar_event_id):
                return

            # Check appointment type restriction
            if not record.calendar_event_id.appointment_type_id:
                return

            if not record.calendar_event_id.appointment_type_id.x_appointment_ref:
                return

            if record.calendar_event_id.appointment_type_id.x_appointment_ref not in ALL_APPOINTMENT_REFS:
                return

            # Initialize empty list with 5 elements
            name_parts = [''] * 5

            # If there's an existing name, try to parse it
            current_name = record.calendar_event_id.name or ''
            if current_name and '/' in current_name:
                current_parts = current_name.split('/')
                # Copy existing parts, up to the length of our target list
                for i in range(min(len(current_parts), 5)):
                    name_parts[i] = current_parts[i]

            # Check for SMS confirmation answer
            sms_icon = ''
            sms_question = self.env['appointment.question'].search([
                ('display_name', '=', 'Confirmation du rendez-vous par SMS')
            ], limit=1)

            if sms_question:
                sms_answer = self.env['appointment.answer.input'].search([
                    ('calendar_event_id', '=', record.calendar_event_id.id),
                    ('question_id', '=', sms_question.id),
                    ('value_answer_id', '!=', False)
                ], limit=1)

                if sms_answer and sms_answer.value_answer_id.name.lower() == 'oui':
                    sms_icon = '📞'
                    _logger.info("SMS confirmation detected for calendar event ID %s",
                               record.calendar_event_id.id)

            # Update specific part based on the question
            if record.question_id.display_name == 'Besoin':
                # Get all answers for the same question (will be one for radio, multiple for checkbox)
                answers = self.env['appointment.answer.input'].search([
                    ('calendar_event_id', '=', record.calendar_event_id.id),
                    ('question_id', '=', record.question_id.id),
                    ('value_answer_id', '!=', False)
                ])
                selected_answers = []
                for answer in answers:
                    if answer.value_answer_id:
                        selected_answers.append(answer.value_answer_id.name)
                name_parts[3] = '+'.join(selected_answers) if selected_answers else ''
                _logger.info("Updated 'Besoin' field for event ID %s: %s",
                           record.calendar_event_id.id, name_parts[3])

            elif record.question_id.display_name == 'Code Postale':
                name_parts[1] = record.value_text_box if record.value_text_box else ''
                _logger.info("Updated postal code for event ID %s: %s",
                           record.calendar_event_id.id, name_parts[1])

            # Get other components that don't come from questions
            name_parts[4] = record.calendar_event_id.user_id.name or name_parts[4]  # Vendeur
            name_parts[0] = record.partner_id.name or name_parts[0]  # Nom Client
            name_parts[2] = record.partner_id.phone or name_parts[2]  # Téléphone

            # Format the new title, filter out empty strings and add SMS icon if needed
            new_title = sms_icon + '/'.join(filter(None, name_parts))

            if new_title and new_title != current_name:
                record.calendar_event_id.with_context(skip_calendar_automation=True).write({'name': new_title})
                _logger.info("Updated appointment title for event ID %s: %s",
                           record.calendar_event_id.id, new_title)

        except Exception as e:
            _logger.error("Update Appointment Title - Error processing record ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _set_partner_on_behalf(self, record):
        """
        Set Partner On Behalf - Automation Rule
        Sets the "rendez-vous pris à la place de" field based on appointment answer
        Only matches partners with "Call Center" category tag
        Only applies to appointment types: APT-ENERG-CNT, APT-NISOL-CNT
        """
        try:
            # Only process if this is the relevant question about "on behalf of partner"
            if not (record.question_id and record.question_id.display_name == 'Rendez-vous pris à la place de'):
                return

            # We need to make sure the record has a calendar_event_id
            if not (record.calendar_event_id and record.calendar_event_id.appointment_type_id):
                return

            # Check appointment type restriction
            if not record.calendar_event_id.appointment_type_id.x_appointment_ref:
                return

            if record.calendar_event_id.appointment_type_id.x_appointment_ref not in CALL_CENTER_APPOINTMENT_REFS:
                return

            # For dropdown/selection questions, use value_answer_id instead of value_text_box
            if record.value_answer_id:
                partner_name = record.value_answer_id.name.strip()

                if partner_name:
                    # Search for the specific category/tag
                    target_category = self.env['res.partner.category'].search([
                        ('name', '=', 'Call Center')
                    ], limit=1)

                    partner = None
                    if target_category:
                        # STRICT: Only exact match with category filter
                        partner = self.env['res.partner'].search([
                            ('name', '=ilike', partner_name),
                            ('category_id', 'in', target_category.ids)
                        ], limit=1)
                        _logger.info("Searching for Call Center partner: '%s'", partner_name)
                    else:
                        _logger.warning("Call Center category not found in system")

                    # If partner found, update the calendar event
                    if partner:
                        # Only update if the field value has changed
                        current_partner = record.calendar_event_id.x_studio_rendez_vous_pris_la_place_de
                        if current_partner != partner:
                            record.calendar_event_id.with_context(skip_calendar_automation=True).write({
                                'x_studio_rendez_vous_pris_la_place_de': partner.id
                            })
                            _logger.info("Set 'rendez-vous pris la place de' to partner: %s (ID: %s) for event ID %s",
                                       partner.name, partner.id, record.calendar_event_id.id)
                    else:
                        # Partner not found - log warning
                        category_name = target_category.name if target_category else 'Category not found'
                        _logger.warning("Partner not found for name: '%s' with category: '%s' (Event ID: %s)",
                                      partner_name, category_name, record.calendar_event_id.id)

            # If no answer provided, clear the field
            else:
                if record.calendar_event_id.x_studio_rendez_vous_pris_la_place_de:
                    record.calendar_event_id.with_context(skip_calendar_automation=True).write({
                        'x_studio_rendez_vous_pris_la_place_de': False
                    })
                    _logger.info("Cleared 'rendez-vous pris la place de' field for event ID %s",
                               record.calendar_event_id.id)

        except Exception as e:
            _logger.error("Set Partner On Behalf - Error processing record ID %s: %s",
                        record.id, str(e), exc_info=True)
