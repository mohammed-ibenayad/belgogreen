# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Assign a SIM- reference to any existing pv.simulation records that
    were left with the placeholder name 'New' (e.g. created before the
    sequence override was active)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    simulations = env['pv.simulation'].search([('name', '=', 'New')])
    if not simulations:
        return

    _logger.info("Renaming %s pv.simulation records still labelled 'New'.", len(simulations))
    sequence = env['ir.sequence']
    for simulation in simulations:
        new_name = sequence.next_by_code('pv.simulation')
        if new_name:
            simulation.name = new_name
