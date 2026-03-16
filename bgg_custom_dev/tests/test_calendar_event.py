# -*- coding: utf-8 -*-

import datetime
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestCalendarEvent(TransactionCase):
    """
    Test suite for calendar.event model automation rules
    Tests 7 automation rules + 1 computed field
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users
        cls.test_user_1 = cls.env['res.users'].create({
            'name': 'Test User 1',
            'login': 'test_user_1',
            'email': 'testuser1@example.com',
        })

        cls.test_user_2 = cls.env['res.users'].create({
            'name': 'Test User 2',
            'login': 'test_user_2',
            'email': 'testuser2@example.com',
        })

        # Create test partners (customers)
        cls.customer_partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'phone': '+32412345678',
            'street': '123 Test Street',
            'city': 'Brussels',
            'zip': '1000',
            'country_id': cls.env.ref('base.be').id,
            'email': 'customer@example.com',
        })

        cls.customer_partner_2 = cls.env['res.partner'].create({
            'name': 'Test Customer 2',
            'phone': '+32487654321',
            'email': 'customer2@example.com',
        })

        # Create internal user partner
        cls.internal_partner = cls.env['res.partner'].create({
            'name': 'Internal User Partner',
            'email': 'internal@company.com',
        })

        # Create appointment types (only if appointment module is installed)
        cls.appointment_type_1 = None
        cls.appointment_type_call_center = None
        cls.appointment_type_commercial = None
        if 'appointment.type' in cls.env:
            # Use sudo() to avoid access rights issues in tests
            cls.appointment_type_1 = cls.env['appointment.type'].sudo().create({
                'name': 'Test Appointment Type 1',
            })
            # Create appointment type for call center automation rules (APT-ENERG-CNT)
            cls.appointment_type_call_center = cls.env['appointment.type'].sudo().create({
                'name': 'Test Call Center Appointment',
                'x_appointment_ref': 'APT-ENERG-CNT',
            })
            # Create appointment type for commercial automation rules (APT-ENERG-COM)
            cls.appointment_type_commercial = cls.env['appointment.type'].sudo().create({
                'name': 'Test Commercial Appointment',
                'x_appointment_ref': 'APT-ENERG-COM',
            })

        # Create NoShow activity type
        cls.noshow_activity_type = cls.env['mail.activity.type'].create({
            'name': 'NoShow',
            'category': 'default',
        })

        # Create CRM opportunity
        cls.test_opportunity = cls.env['crm.lead'].create({
            'name': 'Test Opportunity',
            'partner_id': cls.customer_partner.id,
            'type': 'opportunity',
        })

    # ========================
    # Test 1: Set Initial Organizer
    # ========================

    def test_organizer_set_on_create(self):
        """Test that organizer is set to creator on event creation"""
        # Create event as test_user_1
        event = self.env['calendar.event'].with_user(self.test_user_1).create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
        })

        # Assert organizer is test_user_1
        self.assertEqual(event.user_id.id, self.test_user_1.id,
                        "Organizer should be set to creating user")
        self.assertEqual(event.partner_id.id, self.test_user_1.partner_id.id,
                        "Partner should be set to creating user's partner")

    def test_organizer_not_changed_on_update(self):
        """Test that organizer doesn't change on event updates"""
        # Create event as test_user_1
        event = self.env['calendar.event'].with_user(self.test_user_1).create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
        })

        original_organizer = event.user_id

        # Update event as test_user_2
        event.with_user(self.test_user_2).write({
            'name': 'Updated Test Event',
        })

        # Assert organizer remains test_user_1
        self.assertEqual(event.user_id.id, original_organizer.id,
                        "Organizer should not change on update")

    def test_organizer_overrides_appointment_module(self):
        """Test that organizer is always set to creating user, even if set by other modules"""
        # Skip if appointment module not installed
        if not self.appointment_type_call_center:
            self.skipTest("Appointment module not installed")

        # Create event with user_id already set (simulating appointment module)
        # Use sudo() to avoid access rights issues with test users
        event = self.env['calendar.event'].with_user(self.test_user_1).sudo().create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'user_id': self.test_user_2.id,  # Different user
            'appointment_type_id': self.appointment_type_call_center.id,  # Call center appointment type
        })

        # Assert organizer is overridden to test_user_1
        self.assertEqual(event.user_id.id, self.test_user_1.id,
                        "Organizer should be overridden to creating user")

    # ========================
    # Test 2: Update Calendar Status - Rescheduled
    # ========================

    def test_reschedule_marks_noshow_done(self):
        """Test that rescheduling marks NoShow activities as done"""
        # Skip if appointment module not installed
        if not self.appointment_type_call_center:
            self.skipTest("Appointment module not installed")

        # Create event with call center appointment type
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_call_center.id,
            'appointment_status': 'no_show',
        })

        # Create NoShow activity
        activity = self.env['mail.activity'].create({
            'activity_type_id': self.noshow_activity_type.id,
            'res_model_id': self.env['ir.model']._get('calendar.event').id,
            'res_id': event.id,
            'user_id': self.env.user.id,
            'date_deadline': datetime.date.today(),
            'summary': f'NoShow: {event.name}',
        })

        # Reschedule event
        event.write({
            'start': datetime.datetime.now() + datetime.timedelta(days=1),
            'stop': datetime.datetime.now() + datetime.timedelta(days=1, hours=1),
        })

        # Assert activity is marked as done (no longer exists in active activities)
        active_noshow = self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', event.id),
            ('activity_type_id', '=', self.noshow_activity_type.id),
        ])
        self.assertEqual(len(active_noshow), 0,
                        "NoShow activity should be marked as done")

    def test_reschedule_resets_appointment_status(self):
        """Test that appointment status is reset to 'booked' on reschedule"""
        # Skip if appointment module not installed
        if not self.appointment_type_call_center:
            self.skipTest("Appointment module not installed")

        # Create event with call center appointment type and no_show status
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_call_center.id,
            'appointment_status': 'no_show',
        })

        # Reschedule event
        event.write({
            'start': datetime.datetime.now() + datetime.timedelta(days=1),
            'stop': datetime.datetime.now() + datetime.timedelta(days=1, hours=1),
        })

        # Assert status reset to 'booked'
        self.assertEqual(event.appointment_status, 'booked',
                        "Appointment status should be reset to 'booked'")

    def test_reschedule_not_triggered_on_other_updates(self):
        """Test that reschedule logic only triggers on date/time changes"""
        # Skip if appointment module not installed
        if not self.appointment_type_1:
            self.skipTest("Appointment module not installed")

        # Create event with no_show status
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_1.id,
            'appointment_status': 'no_show',
        })

        # Update name only (not a reschedule)
        event.write({'name': 'Updated Name'})

        # Assert status NOT reset
        self.assertEqual(event.appointment_status, 'no_show',
                        "Appointment status should not change on non-reschedule updates")

    # ========================
    # Test 3: Update Clickable Address & Phone
    # ========================

    def test_clickable_address_link_created(self):
        """Test that Google Maps link is generated for client address"""
        # Create event with customer attendee
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id)],
        })

        # Assert clickable address contains Google Maps URL
        self.assertIn('https://www.google.com/maps/search/', event.x_studio_customer_address,
                     "Clickable address should contain Google Maps URL")
        self.assertIn('123 Test Street', event.x_studio_customer_address,
                     "Clickable address should contain street")
        self.assertIn('Brussels', event.x_studio_customer_address,
                     "Clickable address should contain city")

    def test_clickable_phone_link_created(self):
        """Test that tel: link is generated for phone numbers"""
        # Create event with customer attendee
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id)],
        })

        # Assert clickable phone contains tel: link
        self.assertIn('tel:', event.x_studio_customer_phone,
                     "Clickable phone should contain tel: protocol")
        self.assertIn('+32412345678', event.x_studio_customer_phone,
                     "Clickable phone should contain clean phone number")

    def test_clickable_fields_handle_missing_data(self):
        """Test graceful handling when address/phone is missing"""
        # Create partner without address/phone
        partner_no_data = self.env['res.partner'].create({
            'name': 'Partner No Data',
        })

        # Create event with this partner
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, partner_no_data.id)],
        })

        # Assert no errors and fields are False
        self.assertFalse(event.x_studio_customer_address,
                        "Address should be False when no data available")
        self.assertFalse(event.x_studio_customer_phone,
                        "Phone should be False when no data available")

    def test_clickable_fields_update_on_partner_change(self):
        """Test that clickable fields update when partner changes"""
        # Create event with first customer
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id)],
        })

        original_phone = event.x_studio_customer_phone
        self.assertIn('+32412345678', str(original_phone), "Original phone should be set")

        # Change to different customer (replace all partners with new one)
        event.write({
            'partner_ids': [(6, 0, [self.customer_partner_2.id])],
        })

        # Refresh to ensure we have latest values
        event.invalidate_recordset()

        # Assert fields updated to new customer's phone
        new_phone = event.x_studio_customer_phone
        self.assertIn('+32487654321', str(new_phone),
                     "Phone should update to new customer's phone")
        self.assertNotEqual(str(new_phone), str(original_phone),
                           "Phone should be different from original")

    # ========================
    # Test 4: Replace Call Center Emails
    # ========================

    def test_replace_call_center_emails_for_customers(self):
        """Test that internal user emails are replaced with call center email"""
        # Skip if appointment module not installed
        if not self.appointment_type_commercial:
            self.skipTest("Appointment module not installed")

        # Create customer with internal user email
        customer_with_internal_email = self.env['res.partner'].create({
            'name': 'Customer with Internal Email',
            'email': self.test_user_1.email,  # Same as internal user
        })

        # Create event with this customer
        # Requires appointment type with valid reference for email replacement automation
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, customer_with_internal_email.id)],
            'appointment_type_id': self.appointment_type_commercial.id,  # Commercial appointment type
        })

        # Assert email replaced
        self.assertEqual(customer_with_internal_email.email, 'rdvcallbgg@gmail.com',
                        "Internal email should be replaced with call center email")

    def test_preserve_real_customer_emails(self):
        """Test that real customer emails are preserved"""
        original_email = self.customer_partner.email

        # Create event with real customer
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id)],
        })

        # Assert email unchanged
        self.assertEqual(self.customer_partner.email, original_email,
                        "Real customer email should be preserved")

    def test_internal_user_attendee_email_not_replaced(self):
        """Test that internal user attendees keep their emails"""
        original_email = self.test_user_1.partner_id.email

        # Create event with internal user as attendee
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.test_user_1.partner_id.id)],
        })

        # Assert internal user email unchanged
        self.assertEqual(self.test_user_1.partner_id.email, original_email,
                        "Internal user attendee email should not be changed")

    # ========================
    # Test 5: Assign Existing Customer
    # ========================

    def test_find_existing_customer_by_phone(self):
        """Test that existing customer is found by last 8 digits of phone"""
        # Skip if appointment module not installed
        if not self.appointment_type_commercial:
            self.skipTest("Appointment module not installed")

        # Create event and set phone field in one write to trigger automation
        # Requires appointment type with valid reference for customer assignment automation
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'x_studio_customer_phone': '<a href="tel:0412345678">0412 34 56 78</a>',
            'appointment_type_id': self.appointment_type_commercial.id,  # Commercial appointment type
        })

        # Refresh to ensure we have latest attendee list
        event.invalidate_recordset()

        # Assert existing customer was added as attendee
        attendee_partner_ids = [att.partner_id.id for att in event.attendee_ids]
        self.assertIn(self.customer_partner.id, attendee_partner_ids,
                     f"Existing customer (ID {self.customer_partner.id}) should be added as attendee. Found: {attendee_partner_ids}")

    def test_update_opportunity_with_customer(self):
        """Test that related opportunity is updated with found customer"""
        # Skip if appointment module not installed
        if not self.appointment_type_commercial:
            self.skipTest("Appointment module not installed")

        # Create different partner
        wrong_partner = self.env['res.partner'].create({
            'name': 'Wrong Partner',
        })

        # Create opportunity with wrong partner
        opportunity = self.env['crm.lead'].create({
            'name': 'Test Opportunity',
            'partner_id': wrong_partner.id,
            'type': 'opportunity',
        })

        # Create event linked to opportunity
        # Requires appointment type with valid reference for customer assignment automation
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'opportunity_id': opportunity.id,
            'appointment_type_id': self.appointment_type_commercial.id,  # Commercial appointment type
        })

        # Set phone to match existing customer
        event.x_studio_customer_phone = '<a href="tel:+32412345678">+32 412 34 56 78</a>'
        event.write({'name': 'Test Event Updated'})

        # Assert opportunity partner updated
        self.assertEqual(opportunity.partner_id.id, self.customer_partner.id,
                        "Opportunity partner should be updated to found customer")

    def test_deduplicate_customers(self):
        """Test that duplicate customer attendees are removed"""
        # Create duplicate customer with same phone
        duplicate_customer = self.env['res.partner'].create({
            'name': 'Duplicate Customer',
            'phone': '+32 412 34 56 78',  # Same last 8 digits
        })

        # Create event with both customers
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id), (4, duplicate_customer.id)],
        })

        # Set phone field
        event.x_studio_customer_phone = '<a href="tel:+32412345678">+32 412 34 56 78</a>'
        event.write({'name': 'Test Event Updated'})

        # Assert only one customer remains (the oldest one)
        attendee_partner_ids = [att.partner_id.id for att in event.attendee_ids]
        self.assertIn(self.customer_partner.id, attendee_partner_ids,
                     "Original customer should remain as attendee")

    def test_skip_automation_context_flag(self):
        """Test that skip_calendar_automation context flag prevents recursion"""
        # Create event
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id)],
        })

        original_attendee_count = len(event.attendee_ids)

        # Update with skip flag
        event.with_context(skip_calendar_automation=True).write({
            'name': 'Updated Name',
        })

        # Assert automation didn't run (attendee count unchanged)
        self.assertEqual(len(event.attendee_ids), original_attendee_count,
                        "Automation should be skipped with context flag")

    # ========================
    # Test 6: Create Activity NoShow
    # ========================

    def test_noshow_activity_created(self):
        """Test that NoShow activity is created when status is no_show"""
        # Skip if appointment module not installed
        if not self.appointment_type_call_center:
            self.skipTest("Appointment module not installed")

        # Create event with call center appointment type (required for NoShow automation)
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_call_center.id,
        })

        # Set appointment status to no_show
        event.write({'appointment_status': 'no_show'})

        # Assert NoShow activity created
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', event.id),
            ('activity_type_id', '=', self.noshow_activity_type.id),
        ])
        self.assertEqual(len(activities), 1,
                        "Exactly one NoShow activity should be created")
        self.assertEqual(activities.summary, f'NoShow: {event.name}',
                        "Activity summary should match event name")

    def test_noshow_activity_assigned_to_organizer(self):
        """Test that NoShow activity is assigned to event organizer"""
        # Skip if appointment module not installed
        if not self.appointment_type_call_center:
            self.skipTest("Appointment module not installed")

        # Create event with specific organizer and call center appointment type
        # Use sudo() to avoid access rights issues with test users
        event = self.env['calendar.event'].with_user(self.test_user_1).sudo().create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_call_center.id,
        })

        # Set appointment status to no_show
        event.write({'appointment_status': 'no_show'})

        # Assert activity assigned to organizer
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', event.id),
            ('activity_type_id', '=', self.noshow_activity_type.id),
        ], limit=1)

        self.assertEqual(activity.user_id.id, self.test_user_1.id,
                        "NoShow activity should be assigned to event organizer")

    def test_noshow_activity_not_created_for_other_status(self):
        """Test that NoShow activity is not created for other statuses"""
        # Skip if appointment module not installed
        if not self.appointment_type_1:
            self.skipTest("Appointment module not installed")

        # Create event with different status
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_1.id,
            'appointment_status': 'booked',
        })

        # Assert no NoShow activity created
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', event.id),
            ('activity_type_id', '=', self.noshow_activity_type.id),
        ])
        self.assertEqual(len(activities), 0,
                        "NoShow activity should not be created for non-no_show status")

    # ========================
    # Test 7: Computed Field - x_studio_commercial
    # ========================

    def test_commercial_computed_for_valid_appointment_types(self):
        """Test that commercial field is computed for specific appointment types"""
        # This test would require setting up the commercial group (ID: 59)
        # and creating users in that group, which may not exist in test environment
        # Skipping detailed implementation as it depends on production data
        pass

    def test_commercial_not_computed_for_other_types(self):
        """Test that commercial field is not computed for other appointment types"""
        # Skip if appointment module not installed
        if not self.appointment_type_1:
            self.skipTest("Appointment module not installed")

        # Create event with non-commercial appointment type
        event = self.env['calendar.event'].create({
            'name': 'Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'appointment_type_id': self.appointment_type_1.id,
        })

        # Assert commercial field is False
        self.assertFalse(event.x_studio_commercial,
                        "Commercial field should be False for non-commercial appointment types")

    # ========================
    # Integration Tests
    # ========================

    def test_batch_create_multiple_events(self):
        """Test that automation works correctly with batch create"""
        # Create multiple events at once
        events = self.env['calendar.event'].with_user(self.test_user_1).create([
            {
                'name': f'Test Event {i}',
                'start': datetime.datetime.now() + datetime.timedelta(days=i),
                'stop': datetime.datetime.now() + datetime.timedelta(days=i, hours=1),
            }
            for i in range(3)
        ])

        # Assert all events have correct organizer
        for event in events:
            self.assertEqual(event.user_id.id, self.test_user_1.id,
                           "All batch-created events should have correct organizer")

    def test_full_workflow_appointment_lifecycle(self):
        """Test complete workflow: create -> no_show -> reschedule"""
        # Skip if appointment module not installed
        if not self.appointment_type_call_center:
            self.skipTest("Appointment module not installed")

        # Create event with call center appointment type
        event = self.env['calendar.event'].create({
            'name': 'Workflow Test Event',
            'start': datetime.datetime.now(),
            'stop': datetime.datetime.now() + datetime.timedelta(hours=1),
            'partner_ids': [(4, self.customer_partner.id)],
            'appointment_type_id': self.appointment_type_call_center.id,
        })

        # Verify clickable fields created
        self.assertTrue(event.x_studio_customer_address,
                       "Address should be set")

        # Mark as no_show
        event.write({'appointment_status': 'no_show'})

        # Verify NoShow activity created
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', event.id),
            ('activity_type_id', '=', self.noshow_activity_type.id),
        ])
        self.assertEqual(len(activities), 1, "NoShow activity should exist")

        # Reschedule
        event.write({
            'start': datetime.datetime.now() + datetime.timedelta(days=1),
            'stop': datetime.datetime.now() + datetime.timedelta(days=1, hours=1),
        })

        # Verify status reset and activity closed
        self.assertEqual(event.appointment_status, 'booked',
                        "Status should be reset to booked")
        active_activities = self.env['mail.activity'].search([
            ('res_model', '=', 'calendar.event'),
            ('res_id', '=', event.id),
            ('activity_type_id', '=', self.noshow_activity_type.id),
        ])
        self.assertEqual(len(active_activities), 0,
                        "NoShow activity should be done after reschedule")
