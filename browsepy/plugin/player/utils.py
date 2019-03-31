# -*- coding: UTF-8 -*-

import os
import os.path
import functools

ppath = functools.partial(
    os.path.join,
    os.path.dirname(os.path.realpath(__file__)),
    )
