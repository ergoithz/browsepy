#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import itertools

PY_LEGACY = sys.version_info[0] < 3
if PY_LEGACY:
    FileNotFoundError = type('FileNotFoundError', (OSError,), {})
    range = xrange
    filter = itertools.ifilter
else:
    FileNotFoundError = FileNotFoundError
    range = range
    filter = filter
