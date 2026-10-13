# -*- coding: utf-8 -*-

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Fill the new x_was_confirmed flag on existing orders: confirmed orders,
    and cancelled orders that were confirmed before (status history in the
    chatter, or a posted invoice). Cancelled quotes that were never confirmed
    stay unticked and are no longer counted as cancelled sales."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("UPDATE sale_order SET x_was_confirmed = TRUE WHERE state IN ('sale', 'done')")
    confirmed = cr.rowcount

    # The status tracking stores the selection label in the language of the
    # user who made the change: look for the "confirmed" labels of every
    # installed language (and the technical keys, to be safe).
    labels = {'sale', 'done'}
    for code, _name in env['res.lang'].get_installed():
        selection = env['sale.order'].with_context(lang=code).fields_get(['state'])['state']['selection']
        labels.update(label for key, label in selection if key in ('sale', 'done'))
    labels = list(labels)

    cr.execute("""
        UPDATE sale_order so
           SET x_was_confirmed = TRUE
         WHERE so.state = 'cancel'
           AND (
                EXISTS (
                    SELECT 1
                      FROM mail_tracking_value tv
                      JOIN mail_message m ON m.id = tv.mail_message_id
                      JOIN ir_model_fields f ON f.id = tv.field_id
                     WHERE m.model = 'sale.order'
                       AND m.res_id = so.id
                       AND f.model = 'sale.order'
                       AND f.name = 'state'
                       AND (tv.old_value_char = ANY(%s) OR tv.new_value_char = ANY(%s))
                )
                OR EXISTS (
                    SELECT 1
                      FROM sale_order_line sol
                      JOIN sale_order_line_invoice_rel rel ON rel.order_line_id = sol.id
                      JOIN account_move_line aml ON aml.id = rel.invoice_line_id
                      JOIN account_move am ON am.id = aml.move_id
                     WHERE sol.order_id = so.id
                       AND am.state = 'posted'
                )
           )
    """, [labels, labels])
    cancelled_after = cr.rowcount
    cr.execute("SELECT count(*) FROM sale_order WHERE state = 'cancel' AND NOT COALESCE(x_was_confirmed, FALSE)")
    cancelled_quotes = cr.fetchone()[0]
    _logger.info(
        "BGG x_was_confirmed: %s confirmed orders, %s cancelled after confirmation, "
        "%s cancelled quotes (never confirmed, no longer counted as cancelled sales).",
        confirmed, cancelled_after, cancelled_quotes)
