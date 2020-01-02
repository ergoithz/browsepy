"""Utility functions for playlist files."""

import sys
import codecs
import os.path
import warnings

from six.moves import configparser, range

from browsepy.file import underscore_replace, check_under_base


configparser_class = getattr(
    configparser,
    'SafeConfigParser',
    configparser.ConfigParser
    )
configparser_option_exceptions = (
    configparser.NoSectionError,
    configparser.NoOptionError,
    ValueError,
    )


def normalize_playable_path(path, node):
    """
    Fix path of playable file from a playlist.

    :param path: absolute or relative path or uri
    :type path: str
    :param node: node where path was found
    :type node: browsepy.file.Node
    :returns: absolute path or uri
    :rtype: str or None
    """
    if '://' in path:
        return path
    path = os.path.normpath(path)
    if not os.path.isabs(path):
        return os.path.join(node.parent.path, path)
    drive = os.path.splitdrive(path)[0]
    if drive and not os.path.splitdrive(path)[0]:
        path = drive + path
    if check_under_base(path, node.app.config['DIRECTORY_BASE']):
        return path
    return None


def iter_pls_fields(parser, index):
    """Iterate pls entry fields from parser and entry index."""
    for prop, get_value, entry in (
      ('path', parser.get, 'File%d' % index),
      ('duration', parser.getint, 'Length%d' % index),
      ('title', parser.get, 'Title%d' % index),
      ):
        try:
            yield prop, get_value('playlist', entry)
        except configparser_option_exceptions:
            pass


def iter_pls_entries(node):
    """Iterate entries on a PLS playlist file node."""
    with warnings.catch_warnings():
        # We already know about SafeConfigParser deprecation!
        warnings.simplefilter('ignore', category=DeprecationWarning)
        parser = configparser_class()
        parser.read(node.path)
    try:
        maxsize = parser.getint('playlist', 'NumberOfEntries') + 1
    except configparser_option_exceptions:
        maxsize = sys.maxsize
    failures = 0
    for i in range(1, maxsize):
        if failures > 5:
            break
        data = dict(iter_pls_fields(parser, i))
        if not data.get('path'):
            failures += 1
            continue
        data['path'] = normalize_playable_path(data['path'], node)
        if data['path']:
            failures = 0
            yield data


def iter_m3u_entries(node):
    """Iterate entries on a M3U playlist file node."""
    with codecs.open(
      node.path,
      'r',
      encoding='utf-8' if node.path.endswith('.m3u8') else 'ascii',
      errors=underscore_replace
      ) as f:
        data = {}
        for line in filter(None, map(str.rstrip, f)):
            if line.startswith('#EXTINF:'):
                duration, title = line.split(',', 1)
                data.update(
                    duration=None if duration == '-1' else int(duration),
                    title=title,
                    )
            elif not line.startswith('#'):
                path = normalize_playable_path(line, node)
                if path:
                    yield dict(path=path, **data)
                data.clear()
