#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import subprocess
import mimetypes

from .compat import FileNotFoundError, which  # noqa

generic_mimetypes = frozenset(('application/octet-stream', None))
re_mime_validate = re.compile('\w+/\w+(; \w+=[^;]+)*')


def by_python(path):
    mime, encoding = mimetypes.guess_type(path)
    if mime in generic_mimetypes:
        return None
    return "%s%s%s" % (
        mime or "application/octet-stream", "; "
        if encoding else
        "", encoding or ""
        )


if which('file'):
    def by_file(path):
        try:
            output = subprocess.check_output(
                ("file", "-ib", path),
                universal_newlines=True
                ).strip()
            if (
              re_mime_validate.match(output) and
              output not in generic_mimetypes
              ):
                # 'file' command can return status zero with invalid output
                return output
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return None
else:
    def by_file(path):
        return None


def by_default(path):
    return "application/octet-stream"
