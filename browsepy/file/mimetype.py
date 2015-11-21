#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import subprocess
import mimetypes

generic_mimetypes = {'application/octet-stream', None}
re_mime_validate = re.compile('\w+/\w+(; \w+=[^;]+)*')
mimetype_methods = []

@mimetype_methods.append
def mimetypes_library(path):
    mime, encoding = mimetypes.guess_type(path)
    if mime in generic_mimetypes:
        return None
    return "%s%s%s" % (mime or "application/octet-stream", "; " if encoding else "", encoding or "")

@mimetype_methods.append
def unix_file(path):
    try:
        output = subprocess.check_output(("file", "-ib", path)).decode('utf8').strip()
        if re_mime_validate.match(output) and not output in generic_mimetypes:
            # 'file' command can return status zero with invalid output
            return output
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None

def detect_mimetype(path):
    try:
        return next(filter(None, (method(path) for method in mimetype_methods)))
    except StopIteration:
        return "application/octet-stream"
