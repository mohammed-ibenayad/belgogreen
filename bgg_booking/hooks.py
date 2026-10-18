# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def link_call_center_group(env):
    """The "Call Center" role (created by hand, found by name) gets the
    booking right, so its members can use "Prise de RDV"."""
    call_center = env['calendar.event']._find_group_by_name('Call Center')
    if not call_center:
        _logger.warning("bgg_booking: group 'Call Center' not found, give 'Prise de RDV (call center)' by hand")
        return
    call_center.implied_ids |= env.ref('bgg_booking.group_booking_agent')
    _logger.info("bgg_booking: 'Call Center' group now includes 'Prise de RDV (call center)'")
