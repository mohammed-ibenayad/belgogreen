# -*- coding: utf-8 -*-

from . import models


def post_init(env):
    env['dms.access.group']._bgg_refresh_users()
