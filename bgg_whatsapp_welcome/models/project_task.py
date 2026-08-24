# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'bgg_whatsapp_welcome.enabled'
PARAM_TEMPLATE_NAME = 'bgg_whatsapp_welcome.template_name'
PARAM_TASK_NAME = 'bgg_whatsapp_welcome.task_name'

DEFAULT_TEMPLATE_NAME = 'belgogreen_welcome_call'
# Exact task name used by the project template — the typo is intentional and
# must match bgg_custom_dev's welcome-call deadline automation.
DEFAULT_TASK_NAME = 'Welcom call'


class ProjectTask(models.Model):
    _inherit = 'project.task'

    welcome_whatsapp_sent = fields.Boolean(
        string='WhatsApp Welcome Sent',
        copy=False,
        readonly=True,
        help="Set once the WhatsApp welcome message has been queued for this welcome-call task.",
    )
    is_welcome_call_task = fields.Boolean(
        string='Is Welcome Call Task',
        compute='_compute_is_welcome_call_task',
    )

    @api.depends('name')
    def _compute_is_welcome_call_task(self):
        task_name = self._get_welcome_task_name()
        for task in self:
            task.is_welcome_call_task = task.name == task_name

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to queue the WhatsApp welcome message on new welcome-call tasks"""
        records = super().create(vals_list)

        for record in records:
            record._trigger_welcome_whatsapp()

        return records

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @api.model
    def _get_welcome_task_name(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            PARAM_TASK_NAME, DEFAULT_TASK_NAME)

    @api.model
    def _is_welcome_whatsapp_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_ENABLED, 'True')
        return str(value).strip().lower() not in ('false', '0', 'no', 'off')

    @api.model
    def _get_welcome_whatsapp_template(self):
        """Return (template, error_message).

        The template is looked up by its technical name (or display name) from
        the ``bgg_whatsapp_welcome.template_name`` system parameter. Only
        templates approved by Meta can be sent.
        """
        template_name = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_TEMPLATE_NAME, DEFAULT_TEMPLATE_NAME)

        Template = self.env['whatsapp.template'].sudo()
        name_domain = ['|',
                       ('template_name', '=', template_name),
                       ('name', '=', template_name)]

        template = Template.search(
            name_domain + [('status', '=', 'approved')], limit=1, order='id desc')
        if template:
            return template, False

        template = Template.search(name_domain, limit=1, order='id desc')
        if template:
            return Template.browse(), _(
                'the WhatsApp template "%(name)s" exists but is not approved by Meta yet '
                '(current status: %(status)s)',
                name=template_name, status=template.status)
        return Template.browse(), _(
            'no WhatsApp template named "%(name)s" was found — create it in the WhatsApp '
            'app, submit it for approval and sync the templates', name=template_name)

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def _get_welcome_sale_order(self):
        """Return the sale order behind this task, using the same fallback
        chain as the welcome-call deadline automation in bgg_custom_dev."""
        self.ensure_one()

        if 'project_sale_order_id' in self._fields and self.project_sale_order_id:
            return self.project_sale_order_id
        if self.sale_line_id:
            return self.sale_line_id.order_id
        if self.project_id:
            if 'sale_order_id' in self.project_id._fields and self.project_id.sale_order_id:
                return self.project_id.sale_order_id
            if self.project_id.sale_line_id:
                return self.project_id.sale_line_id.order_id
        return self.env['sale.order']

    def _get_welcome_partner(self):
        """Return the customer to greet: the task customer, falling back to
        the sale order customer."""
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        sale_order = self._get_welcome_sale_order()
        return sale_order.partner_id if sale_order else self.env['res.partner']

    def _trigger_welcome_whatsapp(self):
        """Automatic path called on task creation. Never raises: a WhatsApp
        failure must not block sale order confirmation / task creation."""
        self.ensure_one()
        try:
            if not self.is_welcome_call_task or self.welcome_whatsapp_sent:
                return
            if not self._is_welcome_whatsapp_enabled():
                _logger.info(
                    "WhatsApp welcome disabled by system parameter %s; skipping task ID %s",
                    PARAM_ENABLED, self.id)
                return

            sent, detail = self._send_welcome_whatsapp()
            if not sent:
                _logger.warning(
                    "WhatsApp welcome not sent for task ID %s: %s", self.id, detail)
                self.message_post(body=_(
                    'The WhatsApp welcome message could not be sent automatically: %(reason)s. '
                    'Use the "Send WhatsApp Welcome" button to retry once fixed.',
                    reason=detail))
        except Exception as e:
            _logger.error(
                "WhatsApp Welcome - Error processing task ID %s: %s",
                self.id, str(e), exc_info=True)

    def action_send_welcome_whatsapp(self):
        """Manual (re)send from the task form."""
        self.ensure_one()
        sent, detail = self._send_welcome_whatsapp()
        if not sent:
            raise UserError(_(
                'Cannot send the WhatsApp welcome message: %(reason)s', reason=detail))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('WhatsApp welcome message queued for sending.'),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _send_welcome_whatsapp(self):
        """Queue the WhatsApp welcome template for this task's customer.

        Returns a (sent, detail) tuple; ``detail`` holds the human-readable
        reason when ``sent`` is False. Sending goes through the standard
        ``whatsapp.composer`` so the message is logged in the WhatsApp app
        and delivered by the WhatsApp queue/cron.
        """
        self.ensure_one()

        if 'whatsapp.template' not in self.env or 'whatsapp.composer' not in self.env:
            return False, _('the WhatsApp app is not installed on this database')

        template, error = self._get_welcome_whatsapp_template()
        if not template:
            return False, error

        partner = self._get_welcome_partner()
        if not partner:
            return False, _('no customer is linked to this task or its sale order')

        phone = partner.phone or getattr(partner, 'mobile', False)
        if not phone:
            return False, _(
                'customer "%(partner)s" has no phone number', partner=partner.display_name)

        # The template decides which record feeds its variables/phone field.
        if template.model == 'res.partner':
            target = partner
        elif template.model == self._name:
            target = self
        else:
            return False, _(
                'the WhatsApp template "%(name)s" applies to model "%(model)s"; it must '
                'apply to Contact (res.partner) or Task (project.task)',
                name=template.name, model=template.model)

        try:
            composer = self.env['whatsapp.composer'].sudo().with_context(
                active_model=target._name,
                active_ids=target.ids,
            ).create({
                'res_model': target._name,
                'res_ids': str(target.ids),
                'wa_template_id': template.id,
            })
            # _send_whatsapp_template queues through the WhatsApp cron so the
            # HTTP call to Meta happens outside this transaction.
            if hasattr(composer, '_send_whatsapp_template'):
                composer._send_whatsapp_template(force_send_by_cron=True)
            else:
                composer.action_send_whatsapp_template()
        except Exception as e:
            _logger.error(
                "WhatsApp Welcome - Failed to queue message for task ID %s: %s",
                self.id, str(e), exc_info=True)
            return False, str(e)

        self.write({'welcome_whatsapp_sent': True})
        self.message_post(body=_(
            'WhatsApp welcome message queued for %(partner)s (%(phone)s) using template '
            '"%(template)s".',
            partner=partner.display_name, phone=phone, template=template.name))
        _logger.info(
            "WhatsApp welcome queued for task ID %s (partner %s, template %s)",
            self.id, partner.id, template.id)
        return True, False
