#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import sys
import itertools

PY_LEGACY = sys.version_info[0] < 3
if PY_LEGACY:
    FileNotFoundError = type('FileNotFoundError', (OSError,), {})
    range = xrange
    filter = itertools.ifilter
    str_base = basestring
else:
    FileNotFoundError = FileNotFoundError
    range = range
    filter = filter
    str_base = str

def isnonstriterable(iterable):
    return hasattr(iterable, '__iter__') and not isinstance(iterable, str_base)

def which(name,
          env_path=[path.strip('"') for path in os.environ['PATH'].split(os.pathsep)],
          is_executable_fnc=lambda path: (os.path.isfile(path) and os.access(path, os.X_OK))):
    for path in env_path:
        exe_file = os.path.join(path, name)
        if is_executable_fnc(exe_file):
            return exe_file
    return None
