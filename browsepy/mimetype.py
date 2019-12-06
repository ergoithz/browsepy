"""
File mimetype detection functions.

This module exposes an :var:`alternatives` tuple containing an ordered
list of detection strategies, sorted by priority.
"""

import re
import subprocess
import mimetypes

from .compat import FileNotFoundError, which  # noqa

generic_mimetypes = frozenset(('application/octet-stream', None))
re_mime_validate = re.compile(r'\w+/\w+(; \w+=[^;]+)*')


def by_python(path):
    """Get mimetype by file extension using python mimetype database."""
    mime, encoding = mimetypes.guess_type(path)
    if mime in generic_mimetypes:
        return None
    return "%s%s%s" % (
        mime or "application/octet-stream",
        "; " if encoding else "",
        encoding or ""
        )


def by_file(path):
    """Get mimetype by calling file POSIX utility."""
    try:
        output = subprocess.check_output(
            ("file", "-ib", path),
            universal_newlines=True
            ).strip()
        if re_mime_validate.match(output) and output not in generic_mimetypes:
            # 'file' command can return status zero with invalid output
            return output
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def by_default(path):
    """Get default generic mimetype."""
    return "application/octet-stream"


alternatives = (
    (by_python, by_file, by_default)
    if which('file') else
    (by_python, by_default)
    )
