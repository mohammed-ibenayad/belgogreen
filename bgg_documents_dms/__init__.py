# -*- coding: utf-8 -*-

from . import models


def post_init(env):
    env['bgg.documents.dms']._convert()
