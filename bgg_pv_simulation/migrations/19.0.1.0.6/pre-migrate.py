# -*- coding: utf-8 -*-
"""Migrate ``default_monthly_consumption_kwh`` → ``default_annual_consumption_kwh``.

The simulation used to store a *monthly* consumption default (which the
wizard obtained by dividing the annual input by 12). Every caller then
multiplied it back by 12 to reconstruct the annual total, so the field
was annual in all but name.

19.0.1.0.6 renames the column to reflect reality. This pre-migration
copies the stored monthly default × 12 into the new annual column and
drops the obsolete one, so existing records keep the same effective
annual default after upgrading.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'pv_simulation'
          AND column_name = 'default_monthly_consumption_kwh'
        """
    )
    if not cr.fetchone():
        return  # Fresh install or already migrated.

    cr.execute(
        """
        ALTER TABLE pv_simulation
        ADD COLUMN IF NOT EXISTS default_annual_consumption_kwh double precision
        """
    )
    cr.execute(
        """
        UPDATE pv_simulation
        SET default_annual_consumption_kwh = COALESCE(default_monthly_consumption_kwh, 0) * 12
        WHERE default_annual_consumption_kwh IS NULL
           OR default_annual_consumption_kwh = 0
        """
    )
    cr.execute("SELECT COUNT(*) FROM pv_simulation WHERE default_annual_consumption_kwh > 0")
    migrated = cr.fetchone()[0]
    _logger.info(
        "Migrated default_monthly_consumption_kwh × 12 → default_annual_consumption_kwh "
        "on %s pv.simulation records.",
        migrated,
    )

    cr.execute(
        """
        ALTER TABLE pv_simulation
        DROP COLUMN IF EXISTS default_monthly_consumption_kwh
        """
    )
