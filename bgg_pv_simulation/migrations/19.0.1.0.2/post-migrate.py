# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Assign a SIM- reference to any existing pv.simulation records that
    were left with the placeholder name 'New' (e.g. created before the
    sequence override was active)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Simulation = env['pv.simulation']
    simulations = Simulation.search([('name', 'in', ('New', 'Nouveau'))])
    if not simulations:
        return

    _logger.info("Renaming %s pv.simulation records still labelled 'New'.", len(simulations))
    for simulation in simulations:
        simulation.name = Simulation._next_simulation_reference()
