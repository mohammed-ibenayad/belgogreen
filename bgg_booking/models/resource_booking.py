# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools import plaintext2html

# Labels of the questionnaire in the RDV answers summary, in this order (same
# wording as the former Appointments questions).
QUESTION_LABELS = [
    ('x_street', 'Adresse'),
    ('x_zip', 'Code Postale'),
    ('x_city', 'Ville'),
    ('x_country_id', 'Pays'),
    ('x_solar_since', 'Depuis combien de temps les clients ont-ils des panneaux solaires ?'),
    ('x_is_owner', 'Les clients sont-ils bien les propriétaires du bien ?'),
    ('x_spouse_name', 'Nom du conjoint'),
    ('x_spouse_phone', 'Numéro de téléphone du conjoint'),
    ('x_need_ids', 'Besoin'),
    ('x_sms_confirmation', 'Confirmation du rendez-vous par SMS'),
    ('x_comments', 'Commentaires'),
    ('x_on_behalf_id', 'Rendez-vous pris à la place de'),
]
SMS_ICON = '📞 '


class ResourceBooking(models.Model):
    """Call-centre questionnaire on the booking, and the BelGoGreen RDV
    fields on the meeting it creates (bgg_custom_dev rules)."""
    _inherit = 'resource.booking'

    x_rdv_type_id = fields.Many2one(related='type_id.x_rdv_type_id', string='Type de RDV')
    x_street = fields.Char(string='Adresse')
    x_zip = fields.Char(string='Code postal')
    x_city = fields.Char(string='Ville')
    x_country_id = fields.Many2one('res.country', string='Pays')
    x_solar_since = fields.Char(string='Panneaux solaires depuis')
    x_is_owner = fields.Selection([('yes', 'Oui'), ('no', 'Non')], string='Propriétaires du bien')
    x_need_ids = fields.Many2many('bgg.rdv.need', string='Besoin')
    x_comments = fields.Text(string='Commentaires')
    x_spouse_name = fields.Char(string='Nom du conjoint')
    x_spouse_phone = fields.Char(string='Téléphone du conjoint')
    x_sms_confirmation = fields.Boolean(string='Confirmation du RDV par SMS')
    x_on_behalf_id = fields.Many2one(
        'res.partner',
        string='RDV pris à la place de',
        domain="[('category_id.name', '=', 'Call Center')]",
        help="Agent call center pour qui le rendez-vous est pris "
             "(attribution des ventes au call center).",
    )

    # ------------------------------------------------------------------
    # Meeting
    # ------------------------------------------------------------------

    def _bgg_commercial(self):
        """The booked commercial: first user of the booked resources."""
        self.ensure_one()
        return self.combination_id.resource_ids.filtered(
            lambda r: r.resource_type == 'user').user_id[:1]

    def _bgg_answers_summary(self):
        self.ensure_one()
        lines = []
        for fname, label in QUESTION_LABELS:
            value = self[fname]
            if fname == 'x_sms_confirmation':
                if not self.type_id.x_ask_sms_confirmation:
                    continue
                value = 'Oui' if value else 'Non'
            elif not value:
                continue
            elif fname == 'x_need_ids':
                value = ' + '.join(value.mapped('name'))
            elif fname == 'x_is_owner':
                value = dict(self._fields[fname].selection)[value]
            elif hasattr(value, 'display_name'):
                value = value.display_name
            lines.append(f"{label} : {value}")
        return '\n'.join(lines) or False

    def _bgg_meeting_title(self, commercial):
        """"<client>/<code postal>/<téléphone>/<besoins>/<commercial>", as
        built from the Appointments questionnaire."""
        self.ensure_one()
        partner = self.partner_id
        parts = [partner.name, self.x_zip or partner.zip, partner.phone,
                 '+'.join(self.x_need_ids.mapped('name')), commercial.name]
        title = '/'.join(part for part in parts if part)
        return (SMS_ICON if self.x_sms_confirmation else '') + title

    def _prepare_meeting_vals(self):
        vals = super()._prepare_meeting_vals()
        commercial = self._bgg_commercial()
        if commercial:
            vals['user_id'] = commercial.id
        if not self.name:
            vals['name'] = self._bgg_meeting_title(commercial or self.user_id)
        vals.update({
            'x_rdv_type_id': self.x_rdv_type_id.id,
            'x_rdv_answers': self._bgg_answers_summary(),
            'x_studio_rendez_vous_pris_la_place_de': self.x_on_behalf_id.id,
        })
        if not self.meeting_id:
            vals['x_rdv_status'] = 'booked'
        return vals

    # ------------------------------------------------------------------
    # Client: address and spouse contact from the questionnaire
    # ------------------------------------------------------------------

    def _bgg_apply_questionnaire(self):
        # sudo, as Appointments: the call centre books without contact rights
        Partner = self.env['res.partner'].sudo().with_context(mail_create_nosubscribe=True, tracking_disable=True)
        for booking in self.filtered('partner_id'):
            partner = booking.partner_id.sudo()
            address = {
                'street': booking.x_street,
                'zip': booking.x_zip,
                'city': booking.x_city,
                'country_id': booking.x_country_id.id,
            }
            address = {key: value for key, value in address.items()
                       if value and value != (partner[key].id if key == 'country_id' else partner[key])}
            if address:
                partner.write(address)
            if booking.x_spouse_name:
                spouse = Partner.search([('parent_id', '=', partner.id),
                                         ('name', '=ilike', booking.x_spouse_name)], limit=1)
                if not spouse:
                    Partner.create({'name': booking.x_spouse_name, 'parent_id': partner.id,
                                    'is_company': False, 'phone': booking.x_spouse_phone})
                elif booking.x_spouse_phone and spouse.phone != booking.x_spouse_phone:
                    spouse.phone = booking.x_spouse_phone

    def _sync_meeting(self):
        # A cancelled (archived) booking leaves its meeting as it is.
        active = self.filtered('active')
        # the meeting rules (clickable address / phone) read the client
        active._bgg_apply_questionnaire()
        result = super(ResourceBooking, active)._sync_meeting()
        active._bgg_create_opportunities()
        return result

    # ------------------------------------------------------------------
    # CRM opportunity of the RDV (Appointments "create opportunity")
    # ------------------------------------------------------------------

    def _bgg_create_opportunities(self):
        """One opportunity per new RDV, linked to its meeting: the sale order
        made from it finds the RDV (organizer, call-centre attribution)
        through the opportunity. Created in sudo, as Appointments did."""
        for booking in self.filtered(lambda b: b.type_id.x_create_opportunity and b.meeting_id):
            meeting = booking.meeting_id.sudo()
            if meeting.opportunity_id:
                continue
            lead = self.env['crm.lead'].sudo().create({
                'name': meeting.name,
                'type': 'opportunity',
                'partner_id': booking.partner_id.id,
                'user_id': meeting.user_id.id,
                'description': plaintext2html(booking._bgg_answers_summary() or ''),
            })
            meeting.opportunity_id = lead

    # ------------------------------------------------------------------
    # Cancellation: the meeting is kept, as a cancelled RDV
    # ------------------------------------------------------------------

    def action_cancel(self):
        """Archive the booking but keep its meeting with the "Annulé" status:
        the RDV stays in the history, dashboards and reports (OCA deletes
        it). Cancelled RDVs do not block the commercial's slot."""
        self.meeting_id.write({'x_rdv_status': 'cancelled'})
        self.write({'active': False, 'access_token': False})
