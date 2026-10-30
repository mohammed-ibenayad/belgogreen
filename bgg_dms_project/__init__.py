# -*- coding: utf-8 -*-

from . import models


def post_init(env):
    env['project.project']._bgg_link_converted_directories()
