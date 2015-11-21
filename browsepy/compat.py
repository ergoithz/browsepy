#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys

PY_LEGACY = sys.version_info[0] < 3
if PY_LEGACY:
    FileNotFoundError = type('FileNotFoundError', (OSError,), {})
    range = xrange
else:
    FileNotFoundError = FileNotFoundError
    range = range
