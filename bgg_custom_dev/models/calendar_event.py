# -*- coding: utf-8 -*-

import datetime
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Appointment reference constants for automation rules
ALL_APPOINTMENT_REFS = ['APT-ENERG-CNT', 'APT-ENERG-COM', 'APT-NISOL-CNT', 'APT-NISOL-COM']
CALL_CENTER_APPOINTMENT_REFS = ['APT-ENERG-CNT', 'APT-NISOL-CNT']

# No-show treatment workflow
# System parameter holding the commercial's priority window (in days) after the
# appointment is flagged no-show, before it becomes available to the call center.
NOSHOW_WINDOW_PARAM = 'bgg.noshow_commercial_window_days'
NOSHOW_WINDOW_DEFAULT = '2'
# Commercial disposition that locks the call center out (no point recycling).
NOSHOW_DISPOSITION_LOCKING = 'pas_interesse'
# Roles allowed to act, resolved by name (created manually outside the modules).
COMMERCIAL_GROUP_NAME = 'Commercial'
CALL_CENTER_GROUP_NAME = 'Call Center'


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Computed field: Commercial (sales rep) from attendees
    x_studio_commercial = fields.Char(
        string='Commercial',
        compute='_compute_commercial',
        store=False,
        readonly=True
    )

    # Custom fields for clickable customer information
    x_studio_customer_address = fields.Html(
        string='Customer Address',
        help='Clickable address link to Google Maps'
    )

    x_studio_customer_phone = fields.Html(
        string='Customer Phone',
        help='Clickable phone number with tel: protocol'
    )

    # KPI fields for tracking reviews and referrals per appointment
    x_avis_count = fields.Integer(
        string="Nombre d'avis",
        default=0,
        help="Nombre d'avis clients récoltés lors de ce rendez-vous"
    )

    x_recommandation_count = fields.Integer(
        string='Nombre de recommandations',
        default=0,
        help="Nombre de recommandations (parrainages) obtenues lors de ce rendez-vous"
    )

    # Custom field for tracking who made the appointment on behalf of customer
    x_studio_rendez_vous_pris_la_place_de = fields.Many2one(
        'res.partner',
        string='Rendez-vous pris à la place de',
        help='Partner who made the appointment on behalf of the customer (e.g., Call Center agent)'
    )

    # ------------------------------------------------------------------
    # No-show treatment workflow (call-center appointments only)
    # ------------------------------------------------------------------
    # Commercial disposition after the no-show. Replanning the RDV (changing the
    # date) is the "interested" path and is handled by the reschedule automation,
    # so it is not a value here. Only 'pas_interesse' locks the call center out;
    # 'pas_joignable'/'autre'/empty leave it available after the window. Extra
    # detail goes in the standard Odoo chatter note.
    x_noshow_disposition = fields.Selection(
        selection=[
            ('pas_interesse', 'Client pas intéressé'),
            ('pas_joignable', 'Client pas joignable'),
            ('autre', 'Autre (préciser en note)'),
        ],
        string='Suivi commercial No-show',
        tracking=True,
        help="Suivi commercial du no-show. 'Client pas intéressé' retire le "
             "rendez-vous de la file du call center ; les autres cas le laissent "
             "disponible après la fenêtre commerciale. Détails dans la note.",
    )

    # Moment the appointment was flagged no-show (window anchor; set once, not
    # reset by commercial follow-ups).
    x_noshow_date = fields.Datetime(
        string='No-show constaté le',
        readonly=True,
        copy=False,
        help="Date à laquelle le rendez-vous a été marqué no-show. Sert de point "
             "de départ à la fenêtre de priorité commerciale.",
    )

    # Date from which the call center may recycle the no-show (no-show date +
    # window). Not stored: computed on read so a change to the window parameter
    # takes effect immediately (e.g. when opening the event).
    x_noshow_available_date = fields.Datetime(
        string='Disponible call center le',
        compute='_compute_noshow_available_date',
        search='_search_noshow_available_date',
        help="Date à partir de laquelle le call center peut recycler ce no-show, "
             "une fois la fenêtre de priorité commerciale écoulée.",
    )

    # Appointment reference code, surfaced from the type so the form's
    # visibility rule can test it client-side (a view modifier needs a field on
    # the record). Not stored: the type rarely changes and the value is only
    # needed while the form is open.
    x_appointment_ref = fields.Char(
        string='Appointment Reference',
        related='appointment_type_id.x_appointment_ref',
    )

    # View helper: True when the current user may edit the no-show disposition,
    # i.e. a commercial or an Odoo administrator. Mirrors the write guard so the
    # form's read-only state matches who can actually save the field.
    x_user_can_edit_noshow_disposition = fields.Boolean(
        string='Current User Can Edit No-show Disposition',
        compute='_compute_user_can_edit_noshow_disposition',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set organizer and trigger automation rules on new calendar events"""
        # Stamp the no-show anchor inline (no separate write on the event).
        for vals in vals_list:
            if vals.get('appointment_status') == 'no_show' and not vals.get('x_noshow_date'):
                atype_id = vals.get('appointment_type_id')
                atype = self.env['appointment.type'].browse(atype_id).sudo() if atype_id else None
                if atype and atype.x_appointment_ref in CALL_CENTER_APPOINTMENT_REFS:
                    vals['x_noshow_date'] = fields.Datetime.now()

        records = super(CalendarEvent, self).create(vals_list)

        for record in records:
            # Set organizer to the user who created the event (if not already set and not public user)
            # self._set_initial_organizer(record)

            # Process other automation rules
            self._process_calendar_event(record)

        return records

    def write(self, vals):
        """Override write to trigger automation rules on updates"""
        # Only commercials may set/modify the no-show disposition (system/sudo
        # writes bypass this so automations and admins are unaffected).
        if ('x_noshow_disposition' in vals
                and not self.env.su
                and not self.env.user.has_group('base.group_system')
                and not self._user_in_group_named(COMMERCIAL_GROUP_NAME)):
            raise UserError(
                "Seul un commercial peut renseigner le suivi commercial d'un no-show."
            )

        # Hard-enforce the commercial window: a call-center user cannot reschedule
        # a no-show before it is available, nor one marked 'Client pas intéressé'.
        # Only a *real* date change counts — the calendar form re-sends start/stop
        # on every save even when unchanged.
        rescheduled_ids = set()
        if any(f in vals for f in ('start', 'stop', 'start_date', 'stop_date')):
            for record in self:
                if record._vals_change_dates(vals):
                    rescheduled_ids.add(record.id)
                    record._check_call_center_reschedule_allowed()

        # Stamp/clear the no-show anchor inline (no separate write on the event,
        # which can disturb the calendar's date handling).
        self._apply_noshow_date_to_vals(vals)

        result = super(CalendarEvent, self).write(vals)

        # Skip automation processing if we're already in an automated update
        # to prevent infinite recursion
        if not self.env.context.get('skip_calendar_automation'):
            for record in self:
                self._process_calendar_event(
                    record, vals, date_changed=record.id in rescheduled_ids)

        return result

    def _vals_change_dates(self, vals):
        """True when `vals` actually changes one of this event's date fields
        (normalises the incoming values so a re-sent, unchanged value is ignored)."""
        self.ensure_one()
        converters = (
            ('start', fields.Datetime.to_datetime),
            ('stop', fields.Datetime.to_datetime),
            ('start_date', fields.Date.to_date),
            ('stop_date', fields.Date.to_date),
        )
        for field_name, convert in converters:
            if field_name in vals and convert(vals[field_name]) != self[field_name]:
                return True
        return False

    @api.depends('attendee_ids', 'attendee_ids.partner_id', 'appointment_type_id')
    def _compute_commercial(self):
        """
        Compute Commercial field - finds the sales rep (commercial) from attendees
        Only applies to specific appointment types (IDs: 2, 4, 19, 20)
        Looks for attendees whose partner has a user in the Commercial group (ID: 59)
        """
        # Appointment types where we look for a commercial
        valid_appointment_types = [2, 4, 19, 20]
        # Commercial group ID
        commercial_group_id = 59

        for record in self:
            # Check if the record has one of the specified appointment types
            if not record.appointment_type_id or record.appointment_type_id.id not in valid_appointment_types:
                record.x_studio_commercial = False
                continue

            commercial_attendee = False

            # Search through attendees for a commercial
            for attendee in record.attendee_ids:
                partner = attendee.partner_id
                if partner and partner.user_ids:
                    for user in partner.user_ids:
                        if commercial_group_id in user.group_ids.ids:
                            commercial_attendee = partner
                            break
                    if commercial_attendee:
                        break

            record.x_studio_commercial = commercial_attendee.name if commercial_attendee else False

    # ------------------------------------------------------------------
    # No-show treatment helpers
    # ------------------------------------------------------------------

    def _user_in_group_named(self, group_name):
        """Return True when the current user belongs to the named group."""
        group = self._find_group_by_name(group_name)
        return bool(group) and group.id in self.env.user.group_ids.ids

    @api.depends_context('uid')
    def _compute_user_can_edit_noshow_disposition(self):
        # Same set as the write guard (minus sudo, irrelevant in the form):
        # a commercial or an Odoo administrator.
        can_edit = (self._user_in_group_named(COMMERCIAL_GROUP_NAME)
                    or self.env.user.has_group('base.group_system'))
        for record in self:
            record.x_user_can_edit_noshow_disposition = can_edit

    @api.model
    def _find_group_by_name(self, group_name):
        """Find a res.groups by name, robust to its translatable ``name`` field.

        A plain search only matches the value in the current language, which can
        miss a group whose name is stored under another language (e.g. during a
        migration that runs in the system language). Fall back to scanning each
        installed language.
        """
        groups = self.env['res.groups'].sudo()
        # Case-insensitive match: the same group may be stored with different
        # casing per language (e.g. en_US 'commercial' vs fr_BE 'Commercial').
        group = groups.search([('name', '=ilike', group_name)], limit=1)
        if group:
            return group
        for lang_code, _label in self.env['res.lang'].get_installed():
            group = groups.with_context(lang=lang_code).search(
                [('name', '=ilike', group_name)], limit=1)
            if group:
                return group
        return groups.browse()

    @api.model
    def _appointment_ref_of(self, record):
        """Return the appointment ref code, read with sudo.

        Server-side automations must not depend on the saving user's access to
        appointment.type (e.g. a commercial without read access on it raised an
        AccessError on every save), so the ref code is always read in sudo.
        Returns False when there is no type or no ref.
        """
        atype = record.appointment_type_id
        return atype.sudo().x_appointment_ref if atype else False

    def _is_call_center_appointment(self):
        """Return True when this event is a call-center appointment (CNT)."""
        self.ensure_one()
        return self._appointment_ref_of(self) in CALL_CENTER_APPOINTMENT_REFS

    @api.model
    def _noshow_window_days(self):
        """Current commercial priority window, in days (system parameter)."""
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                NOSHOW_WINDOW_PARAM, NOSHOW_WINDOW_DEFAULT))
        except (TypeError, ValueError):
            return int(NOSHOW_WINDOW_DEFAULT)

    @api.depends('x_noshow_date')
    def _compute_noshow_available_date(self):
        """Call center availability = no-show flag date + configurable window.

        Not stored: reads the parameter on each compute so a change to the
        window takes effect immediately when the event is read.
        """
        window_days = self._noshow_window_days()
        for record in self:
            if record.x_noshow_date:
                record.x_noshow_available_date = (
                    record.x_noshow_date + datetime.timedelta(days=window_days))
            else:
                record.x_noshow_available_date = False

    def _search_noshow_available_date(self, operator, value):
        """Make the (non-stored) availability date searchable.

        available = x_noshow_date + window, a constant shift, so
        ``available <op> value`` is equivalent to
        ``x_noshow_date <op> (value - window)`` on the stored anchor. Events
        with no anchor (NULL) are naturally excluded by the comparison, which is
        correct: without a no-show date they are not available.
        """
        window = datetime.timedelta(days=self._noshow_window_days())
        value = fields.Datetime.to_datetime(value)
        return [('x_noshow_date', operator, value - window)]

    def _check_call_center_reschedule_allowed(self):
        """Hard-enforce the commercial window on reschedules.

        A call-center user may not move a no-show's date before it is available,
        nor one the commercial marked 'Client pas intéressé'. Commercials and
        system/sudo writes are unaffected.
        """
        self.ensure_one()
        if self.env.su or self.env.user.has_group('base.group_system'):
            return
        if self.appointment_status != 'no_show' or not self._is_call_center_appointment():
            return
        if not self._user_in_group_named(CALL_CENTER_GROUP_NAME):
            return

        if self.x_noshow_disposition == NOSHOW_DISPOSITION_LOCKING:
            raise UserError(
                "Ce no-show est marqué « Client pas intéressé » : le call center "
                "ne peut pas le replanifier."
            )

        available = self.x_noshow_available_date
        if not available or available > fields.Datetime.now():
            raise UserError(
                "Ce no-show n'est pas encore disponible pour le call center "
                "(fenêtre de priorité commerciale en cours jusqu'au %s)."
                % (available and fields.Datetime.to_string(available) or '—')
            )

    def _apply_noshow_date_to_vals(self, vals):
        """Add the no-show anchor to the *current* write vals (instead of a
        separate write) when the status transitions in/out of no-show.

        Commercial follow-ups don't change the status, so they never touch the
        anchor — the window is not reset by them.
        """
        if 'x_noshow_date' in vals or 'appointment_status' not in vals:
            return
        if vals['appointment_status'] == 'no_show':
            if any(r._is_call_center_appointment() and not r.x_noshow_date for r in self):
                vals['x_noshow_date'] = fields.Datetime.now()
        elif any(r.x_noshow_date for r in self):
            vals['x_noshow_date'] = False

    def _process_calendar_event(self, record, vals=None, date_changed=False):
        """Process all automation rules for calendar events"""
        # Note: Organizer update removed - organizer is set once at creation and never changes
        self._update_calendar_status_rescheduled(record, vals, date_changed=date_changed)
        # IMPORTANT: _assign_existing_customer must run BEFORE _update_clickable_from_attendee
        # because it uses x_studio_customer_phone to find customers, and _update_clickable_from_attendee
        # will clear that field if no client attendees exist yet
        # Only run on create (vals=None) or when relevant fields change
        if vals is None or any(f in vals for f in ('partner_ids', 'x_studio_customer_phone')):
            self._assign_existing_customer(record)
        self._update_clickable_from_attendee(record)
        self._replace_call_center_emails(record)
        self._create_activity_noshow(record)

    def _set_initial_organizer(self, record):
        """
        Set Initial Organizer on Creation - Automation Rule
        Sets the organizer to the user who created the event (never changes after creation)
        Uses create_uid (the user who created the record) as the organizer
        ALWAYS overrides any organizer set by other modules (like appointments)
        Only applies to appointment types: APT-ENERG-CNT, APT-NISOL-CNT
        """
        try:
            # Only applies to call-center appointment types (ref read via sudo).
            if self._appointment_ref_of(record) not in CALL_CENTER_APPOINTMENT_REFS:
                return

            # Use the user who created the record as organizer
            creating_user = record.create_uid

            if creating_user and not creating_user._is_public():
                # Always set organizer to the creating user, even if already set by other modules
                if record.user_id != creating_user or record.partner_id != creating_user.partner_id:
                    record.sudo().with_context(skip_calendar_automation=True).write({
                        'user_id': creating_user.id,
                        'partner_id': creating_user.partner_id.id
                    })
                    _logger.info("Set organizer to creating user: %s (ID: %s) for event ID %s",
                               creating_user.name, creating_user.id, record.id)
                else:
                    _logger.info("Organizer already matches creating user for event ID %s", record.id)
            else:
                _logger.info("Creating user is public or not found, skipping organizer setup for event ID %s", record.id)

        except Exception as e:
            _logger.error("Set Initial Organizer - Error processing event ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _update_calendar_status_rescheduled(self, record, vals=None, date_changed=False):
        """
        Update Calendar Status When Rescheduled - Automation Rule
        Deletes NoShow activities and posts a chatter note when an event is rescheduled
        Only applies to appointment types: APT-ENERG-CNT, APT-NISOL-CNT
        """
        try:
            # Only applies to call-center appointment types (ref read via sudo).
            if self._appointment_ref_of(record) not in CALL_CENTER_APPOINTMENT_REFS:
                return

            # Prevent infinite recursion when processing NoShow activities
            if self.env.context.get('processing_noshow_reschedule'):
                return

            # Only process on a real reschedule. The calendar form re-sends
            # start/stop on every save even when unchanged, so we rely on the
            # caller's value comparison (date_changed) rather than mere presence
            # in vals. On create (vals is None) keep the prior behaviour.
            if vals is not None and not date_changed:
                return

            # Find linked no-show activities
            # Note: No need to filter by state - mail.activity table only contains active (not done) activities
            noshow_activities = self.env['mail.activity'].search([
                ('res_model', '=', 'calendar.event'),
                ('res_id', '=', record.id),
                ('activity_type_id.name', '=', 'NoShow')
            ])

            if noshow_activities:
                _logger.info("Found %s NoShow activities for event ID %s - marking as done",
                           len(noshow_activities), record.id)

                # Set context flag to prevent recursion during activity processing
                ctx = dict(self.env.context, processing_noshow_reschedule=True, skip_calendar_automation=True)

                # Mark activities as done instead of deleting to avoid UI sync errors
                # This prevents "Record does not exist" errors when the UI tries to refresh
                current_user = self.env.user.name
                feedback_message = f"❌ Annulée - NoShow plus applicable suite à la replanification du rendez-vous par {current_user}"

                for activity in noshow_activities:
                    activity.with_context(ctx).action_feedback(feedback=feedback_message)

                _logger.info("Marked %s NoShow activities as done for event ID %s",
                           len(noshow_activities), record.id)
            else:
                ctx = dict(self.env.context, processing_noshow_reschedule=True, skip_calendar_automation=True)

            # Reset the status on every real reschedule of a no-show, regardless
            # of whether an active NoShow activity remained: it may have been
            # closed by an earlier follow-up (so the search above finds nothing),
            # yet replanning the RDV still means the no-show is no longer relevant.
            if record.appointment_status == 'no_show':
                record.sudo().with_context(ctx).write({
                    'appointment_status': 'booked'
                })
                _logger.info("Reset appointment status to 'booked' for event ID %s", record.id)

        except Exception as e:
            _logger.error("Update Calendar Status when Rescheduled - Error processing event ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _update_clickable_from_attendee(self, record):
        """
        Update Clickable Address & Phone from Client Attendee - Automation Rule
        Syncs address and phone from client (non-internal) attendee to calendar event custom fields
        """
        try:
            # Find client attendees: partners not linked to internal users
            client_partner = None
            for attendee in record.attendee_ids:
                partner = attendee.partner_id
                if not partner:
                    continue

                # Check if partner is NOT an internal user
                is_internal = any(
                    user.has_group('base.group_user') for user in partner.user_ids if user.active
                )

                if not is_internal:
                    client_partner = partner
                    break  # Use the first client found

            # Initialize values
            new_address_html = False
            new_phone_html = False

            if client_partner:
                _logger.info("Processing client partner: %s (ID: %s) for event ID %s",
                           client_partner.name, client_partner.id, record.id)

                # --- Build clickable address ---
                addr_parts = []
                if client_partner.street:
                    addr_parts.append(client_partner.street)
                if client_partner.street2:
                    addr_parts.append(client_partner.street2)

                city_zip = ' '.join(filter(None, [client_partner.zip, client_partner.city]))
                if city_zip:
                    addr_parts.append(city_zip)

                if client_partner.country_id:
                    addr_parts.append(client_partner.country_id.name)

                if addr_parts:
                    full_addr = ','.join(addr_parts)
                    encoded_addr = full_addr.replace(' ', '+').replace(',', '%2C')
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_addr}"
                    new_address_html = f'<a href="{maps_url}" target="_blank">{full_addr}</a>'

                # --- Build clickable phone ---
                phone = client_partner.phone
                if phone:
                    clean_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
                    if clean_phone:
                        new_phone_html = f'<a href="tel:{clean_phone}">{phone}</a>'

                # Prepare updates
                update_vals = {}
                if new_address_html != record.x_studio_customer_address:
                    update_vals['x_studio_customer_address'] = new_address_html
                    _logger.info("Updating customer address from attendee for event ID %s: %s",
                               record.id, full_addr if addr_parts else 'cleared')

                if new_phone_html != record.x_studio_customer_phone:
                    update_vals['x_studio_customer_phone'] = new_phone_html
                    _logger.info("Updating customer phone from attendee for event ID %s: %s",
                               record.id, phone if phone else 'cleared')

                # Apply updates in one write (only if needed)
                if update_vals:
                    record.sudo().with_context(skip_calendar_automation=True).write(update_vals)

        except Exception as e:
            _logger.error("Update Clickable Address & Phone from Attendee - Error processing event ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _replace_call_center_emails(self, record):
        """
        Replace Call Center Emails - Automation Rule
        Replaces customer attendee emails that match internal user emails with standard call center email
        Prevents internal user emails from being exposed to customers
        Only applies to appointment types: APT-ENERG-CNT, APT-ENERG-COM, APT-NISOL-CNT, APT-NISOL-COM
        """
        try:
            # Only applies to BGG appointment types (ref read via sudo).
            if self._appointment_ref_of(record) not in ALL_APPOINTMENT_REFS:
                return

            if not record.attendee_ids:
                return

            standard_call_center_email = 'rdvcallbgg@gmail.com'

            # Get all internal users (employees with portal/internal access)
            internal_users = self.env['res.users'].search([
                ('share', '=', False),  # Internal users (not portal users)
                ('active', '=', True)
            ])

            # Get all their emails (normalized to lowercase)
            internal_user_emails = set()
            for user in internal_users:
                if user.email:
                    internal_user_emails.add(user.email.strip().lower())
                # Also check the partner email if different
                if user.partner_id and user.partner_id.email:
                    internal_user_emails.add(user.partner_id.email.strip().lower())

            _logger.info("Checking %s attendees against %s internal emails for event ID %s",
                       len(record.attendee_ids), len(internal_user_emails), record.id)

            # Process each attendee
            for attendee in record.attendee_ids:
                partner = attendee.partner_id

                if not partner or not partner.email:
                    continue

                # Skip if this partner is an internal user themselves (the organizer)
                is_internal_user = any(
                    user.has_group('base.group_user') for user in partner.user_ids if user.active
                )
                if is_internal_user:
                    continue

                # This is a CUSTOMER attendee - check their email
                customer_email = partner.email.strip().lower()

                # Skip if already the standard call center email
                if customer_email == standard_call_center_email.lower():
                    continue

                # Check if customer email matches any internal user email
                if customer_email in internal_user_emails:
                    # This is an internal user email, replace it
                    original_email = partner.email
                    _logger.info("Internal user email detected in CUSTOMER: %s (ID: %s) - Email: %s - Replacing with %s",
                                partner.name, partner.id, original_email, standard_call_center_email)

                    partner.with_context(
                        mail_create_nosubscribe=True,
                        tracking_disable=True
                    ).write({'email': standard_call_center_email})

                    _logger.info("Replaced internal email '%s' with '%s' for CUSTOMER: %s",
                               original_email, standard_call_center_email, partner.name)

        except Exception as e:
            _logger.error("Replace Call Center Emails - Error processing event ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _assign_existing_customer(self, record):
        """
        Assign Existing Customer To Calendar Event and Opportunity - Automation Rule
        Finds existing customers by phone (last 8 digits), assigns them to event and opportunity
        Cleans up duplicate customer records when safe to do so
        Only applies to appointment types: APT-ENERG-CNT, APT-ENERG-COM, APT-NISOL-CNT, APT-NISOL-COM
        """
        try:
            # Only applies to BGG appointment types (ref read via sudo).
            if self._appointment_ref_of(record) not in ALL_APPOINTMENT_REFS:
                return

            phone = None

            # Try to get phone from custom field
            try:
                if record.x_studio_customer_phone:
                    phone_text = record.x_studio_customer_phone
                    if 'tel:' in phone_text:
                        start = phone_text.find('tel:') + 4
                        end = phone_text.find('"', start)
                        if end == -1:
                            end = phone_text.find('>', start)
                        if end > start:
                            phone = phone_text[start:end]
                        else:
                            phone = phone_text[start:].strip()
                    else:
                        phone = phone_text
            except:
                pass

            # Fallback to partner phone
            if not phone and record.partner_id:
                if record.partner_id.phone:
                    phone = record.partner_id.phone

            if phone:
                # Clean phone - keep only digits
                clean_phone = ''.join(c for c in phone if c.isdigit())

                if len(clean_phone) >= 8:
                    last_8_digits = clean_phone[-8:]
                    _logger.info("Searching for existing customer with last 8 digits: %s for event ID %s",
                               last_8_digits, record.id)

                    # Search for existing customers
                    existing_customers = self.env['res.partner'].search([
                        ('phone', 'ilike', last_8_digits)
                    ])

                    # Filter out internal users
                    real_customers = existing_customers.filtered(
                        lambda p: not any(user.has_group('base.group_user') for user in p.user_ids if user.active)
                    )

                    if real_customers:
                        # Sort by creation date - oldest first (most likely the real customer)
                        real_customers = real_customers.sorted(key=lambda p: p.create_date)
                        customer = real_customers[0]

                        _logger.info("Found existing customer: %s (ID: %s) for event ID %s",
                                   customer.name, customer.id, record.id)

                        # Find potential duplicates to clean up
                        potential_duplicates = real_customers.filtered(lambda p: p.id != customer.id)

                        # Also check current attendees for duplicates
                        attendee_partners = [att.partner_id for att in record.attendee_ids if att.partner_id]

                        for attendee_partner in attendee_partners:
                            # If this attendee is not the main customer and has similar phone
                            if attendee_partner.id != customer.id:
                                # Check if it's a duplicate (same last 8 digits)
                                if attendee_partner.phone:
                                    attendee_phone = attendee_partner.phone
                                    attendee_clean = ''.join(c for c in attendee_phone if c.isdigit())
                                    if len(attendee_clean) >= 8 and attendee_clean[-8:] == last_8_digits:
                                        if attendee_partner not in potential_duplicates:
                                            potential_duplicates |= attendee_partner

                        # Check if customer is already an attendee
                        customer_already_attendee = any(
                            attendee.partner_id.id == customer.id
                            for attendee in record.attendee_ids
                        )

                        # Add customer as attendee if not already
                        if not customer_already_attendee:
                            record.with_context(skip_calendar_automation=True).write({'partner_ids': [(4, customer.id)]})
                            _logger.info("Added %s as attendee to event ID %s", customer.name, record.id)

                        # Update opportunity if exists
                        try:
                            if record.opportunity_id:
                                if record.opportunity_id.partner_id.id != customer.id:
                                    record.opportunity_id.write({'partner_id': customer.id})
                                    _logger.info("Updated opportunity partner to: %s for event ID %s",
                                               customer.name, record.id)
                        except:
                            pass

                        # Search for related opportunities
                        opportunities = self.env['crm.lead'].search([('calendar_event_ids', 'in', record.id)])
                        for opp in opportunities:
                            if opp.partner_id.id != customer.id:
                                opp.write({'partner_id': customer.id})
                                _logger.info("Updated opportunity '%s' to customer: %s", opp.name, customer.name)

                        # Clean up duplicates
                        for duplicate in potential_duplicates:
                            _logger.info("Found potential duplicate: %s (ID: %s) for event ID %s",
                                       duplicate.name, duplicate.id, record.id)

                            # Remove from attendees if present
                            duplicate_attendee = record.attendee_ids.filtered(lambda a: a.partner_id.id == duplicate.id)
                            if duplicate_attendee:
                                record.with_context(skip_calendar_automation=True).write({'partner_ids': [(3, duplicate.id)]})
                                _logger.info("Removed duplicate %s from attendees", duplicate.name)

                            # Check if safe to delete
                            other_events = self.env['calendar.event'].search([
                                ('partner_id', '=', duplicate.id),
                                ('id', '!=', record.id)
                            ])

                            # Check attendees in other events
                            other_event_attendees = self.env['calendar.attendee'].search([
                                ('partner_id', '=', duplicate.id),
                                ('event_id', '!=', record.id)
                            ])

                            other_opps = self.env['crm.lead'].search([('partner_id', '=', duplicate.id)])

                            # Only delete if not used elsewhere
                            if not other_events and not other_event_attendees and not other_opps:
                                try:
                                    duplicate_name = duplicate.name
                                    duplicate_id = duplicate.id
                                    duplicate.unlink()
                                    _logger.info("Deleted duplicate partner: %s (ID: %s)", duplicate_name, duplicate_id)
                                except Exception as delete_error:
                                    _logger.warning("Could not delete duplicate %s (ID: %s): %s",
                                                  duplicate.name, duplicate.id, str(delete_error))
                            else:
                                _logger.info("Duplicate %s is used elsewhere, keeping it", duplicate.name)

                        _logger.info("Successfully assigned existing customer: %s to event ID %s",
                                   customer.name, record.id)
                    else:
                        _logger.info("No existing customer found for phone digits: %s", last_8_digits)
                else:
                    _logger.warning("Phone number too short (< 8 digits): %s for event ID %s",
                                  clean_phone, record.id)
            else:
                _logger.info("No phone number found for event ID %s", record.id)

        except Exception as e:
            _logger.error("Assign Existing Customer - Error processing event ID %s: %s",
                        record.id, str(e), exc_info=True)

    def _create_activity_noshow(self, record):
        """
        Create activity for NoShow - Automation Rule
        Creates or updates a NoShow activity when appointment status is set to no_show
        Only applies to appointment types: APT-ENERG-CNT, APT-NISOL-CNT
        """
        try:
            # Only applies to call-center appointment types (ref read via sudo).
            if self._appointment_ref_of(record) not in CALL_CENTER_APPOINTMENT_REFS:
                return

            if record.appointment_status != 'no_show':
                return

            _logger.info("Processing NoShow status for calendar event ID %s", record.id)

            noshow_activity_type = self.env['mail.activity.type'].search([('name', '=', 'NoShow')], limit=1)

            if not noshow_activity_type:
                _logger.warning("NoShow activity type not found in system for event ID %s", record.id)
                return

            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'calendar.event'),
                ('res_id', '=', record.id),
                ('activity_type_id', '=', noshow_activity_type.id)
            ], limit=1)

            # Only create the follow-up on the transition into no-show. If one
            # already exists, leave it untouched: re-writing it on every save
            # needlessly re-stamped the deadline to "today" each time.
            if existing_activity:
                _logger.info("NoShow activity (ID %s) already exists for event ID %s - leaving as-is",
                           existing_activity.id, record.id)
                return

            # Get the event organizer, ensuring we don't assign to public user
            user = self.env.user
            assigned_user = False

            if record.user_id:
                assigned_user = record.user_id
            elif not user._is_public():
                assigned_user = user

            if assigned_user:
                # NOTE: do NOT set `calendar_event_id` here. That field marks the
                # activity as the meeting's *scheduling* activity, which makes core
                # sync the activity deadline onto the event's start/stop and
                # silently rescheduled no-show events to "today" on every save.
                # The activity is already attached to the event via res_model/res_id.
                new_activity = self.env['mail.activity'].create({
                    'activity_type_id': noshow_activity_type.id,
                    'user_id': assigned_user.id,
                    'res_model_id': self.env['ir.model']._get('calendar.event').id,
                    'res_id': record.id,
                    'date_deadline': datetime.datetime.now().date(),
                    'summary': f'NoShow: {record.name or "Rendez-vous (Etude)"}',
                })
                _logger.info("Created new NoShow activity (ID %s) for event ID %s, assigned to user %s",
                           new_activity.id, record.id, assigned_user.name)
            else:
                _logger.warning("No valid user to assign NoShow activity for event ID %s", record.id)

        except Exception as e:
            _logger.error("Create Activity for NoShow - Error processing event ID %s: %s",
                        record.id, str(e), exc_info=True)
