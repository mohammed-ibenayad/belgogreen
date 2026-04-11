# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill the new per-simulation tariff override fields from the
    linked pv.tariff.profile for simulations that already exist."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    simulations = env['pv.simulation'].search([
        ('tariff_profile_id', '!=', False),
        '|', '|',
        ('purchase_price_kwh', '=', 0),
        ('feed_in_tariff_kwh', '=', 0),
        ('battery_cost_kwh', '=', 0),
    ])
    if not simulations:
        return

    _logger.info(
        "Backfilling tariff overrides on %s pv.simulation records.",
        len(simulations),
    )
    for simulation in simulations:
        profile = simulation.tariff_profile_id
        vals = {}
        if not simulation.purchase_price_kwh:
            vals['purchase_price_kwh'] = profile.purchase_price_kwh
        if not simulation.feed_in_tariff_kwh:
            vals['feed_in_tariff_kwh'] = profile.feed_in_tariff_kwh
        if not simulation.battery_cost_kwh:
            vals['battery_cost_kwh'] = profile.battery_cost_kwh
        if vals:
            simulation.with_context(skip_regeneration_flag=True).write(vals)
