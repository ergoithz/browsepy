# -*- coding: UTF-8 -*-


import sys
import codecs
import os.path
import warnings

from six.moves import range, configparser

try:
    from six.moves.configparser import SafeConfigParser as ConfigParser
except ImportError:
    from six.moves.configparser import ConfigParser

from browsepy.file import underscore_replace


CONFIGPARSER_OPTION_EXCEPTIONS = (
    configparser.NoSectionError,
    configparser.NoOptionError,
    ValueError,
    )

def normalize_playable_path(path, node):
    """
    Fixes the path of playable file from a playlist.

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
    drive = os.path.splitdrive(self.path)[0]
    if drive and not os.path.splitdrive(path)[0]:
        path = drive + path
    if check_under_base(path, node.app.config['DIRECTORY_BASE']):
        return path
    return None

def iter_pls_entries(node):
    """Iter entries on a PLS playlist file node."""
    with warnings.catch_warnings():
        # We already know about SafeConfigParser deprecation!
        warnings.simplefilter('ignore', category=DeprecationWarning)
        parser = ConfigParser()
        parser.read(node.path)
    try:
        maxsize = parser.getint('playlist', 'NumberOfEntries')
    except CONFIGPARSER_OPTION_EXCEPTIONS:
        maxsize = sys.maxsize
    failures = 0
    for i in six.moves.range(1, maxsize):
        if failures > 5:
            break
        data = {}
        for prop, field, extract in (
          ('path', 'File%d', parser.get),
          ('duration', 'Length%d', parser.getint),
          ('title', 'Title%d', parser.get),
          ):
            try:
                data[prop] = extract('playlist', field % i)
            except CONFIGPARSER_OPTION_EXCEPTIONS:
                pass
        if data.get('path'):
            failures = 0
            yield data
            continue
        failures += 1

def iter_m3u_entries(node):
    """Iter entries on a M3U playlist file node."""
    data = {}
    with codecs.open(
      node.path,
      'r',
      encoding='utf-8' if node.path.endswith('.m3u8') else 'ascii',
      errors=underscore_replace
      ) as f:
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
                    data['path'] = path
                    yield dict(data)
                data.clear()


