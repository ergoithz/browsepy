# -*- coding: UTF-8 -*-


import sys
import codecs
import os.path
import warnings

import six
import six.moves

from werkzeug.utils import cached_property

from browsepy.file import Node, File, Directory, \
                          underscore_replace, check_under_base


class PLSFileParser(object):
    """
    ConfigParser wrapper accepting fallback on get for convenience.

    This wraps instead of inheriting due ConfigParse being classobj on python2.
    """
    NOT_SET = type('NotSetType', (object,), {})
    option_exceptions = (
        six.moves.configparser.NoSectionError,
        six.moves.configparser.NoOptionError,
        ValueError,
        )
    parser_class = getattr(
        six.moves.configparser,
        'SafeConfigParser',
        six.moves.configparser.ConfigParser
        )

    def __init__(self, path):
        """Initialize."""
        with warnings.catch_warnings():
            # We already know about SafeConfigParser deprecation!
            warnings.simplefilter('ignore', category=DeprecationWarning)
            self._parser = self.parser_class()
        self._parser.read(path)

    def getint(self, section, key, fallback=NOT_SET):
        """Get int from pls file, returning fallback if unable."""
        try:
            return self._parser.getint(section, key)
        except self.option_exceptions:
            if fallback is self.NOT_SET:
                raise
            return fallback

    def get(self, section, key, fallback=NOT_SET):
        """Get value from pls file, returning fallback if unable."""
        try:
            return self._parser.get(section, key)
        except self.option_exceptions:
            if fallback is self.NOT_SET:
                raise
            return fallback


class Playable(Node):
    """Base class for playable nodes."""

    playable_list = False

    @cached_property
    def is_playable(self):
        """
        Get if node is playable.

        :returns: True if node is playable, False otherwise
        :rtype: bool
        """
        print(self)
        return self.playable_check(self)

    def normalize_playable_path(self, path):
        """
        Fixes the path of playable file from a playlist.

        :param path: absolute or relative path or uri
        :type path: str
        :returns: absolute path or uri
        :rtype: str or None
        """
        if '://' in path:
            return path
        path = os.path.normpath(path)
        if not os.path.isabs(path):
            return os.path.join(self.parent.path, path)
        drive = os.path.splitdrive(self.path)[0]
        if drive and not os.path.splitdrive(path)[0]:
            path = drive + path
        if check_under_base(path, self.app.config['DIRECTORY_BASE']):
            return path
        return None

    def _entries(self):
        return ()

    def entries(self, sortkey=None, reverse=None):
        """Get playlist file entries."""
        for node in self._entries():
            if node.is_playable and not node.is_excluded:
                yield node

    @classmethod
    def playable_check(cls, node):
        """Check if class supports node."""
        kls = cls.directory_class if node.is_directory else cls.file_class
        return kls.playable_check(node)


@Playable.register_file_class
class PlayableExtension(Playable):
    """=Generic node for filenames with extension."""

    title = None
    duration = None

    playable_extensions = {}
    playable_extension_classes = []  # deferred

    @cached_property
    def mimetype(self):
        """Get mimetype."""
        print(self)
        return self.detect_mimetype(self.path)

    @classmethod
    def detect_extension(cls, path):
        for extension in cls.playable_extensions:
            if path.endswith('.%s' % extension):
                return extension
        return None

    @classmethod
    def detect_mimetype(cls, path):
        return cls.playable_extensions.get(cls.detect_extension(path))

    @classmethod
    def playable_check(cls, node):
        """Get if file is playable."""
        if cls.generic:
            return any(
                kls.playable_check(node)
                for kls in cls.playable_extension_classes
                )
        return cls.detect_extension(node.path) in cls.playable_extensions

    @classmethod
    def from_node(cls, node, app=None):
        """Get playable node from given node."""
        if cls.generic:
            for kls in cls.playable_classes:
                playable = kls.from_node(node)
                if playable:
                    return playable
            return node
        return kls(node.path, node.app)

    @classmethod
    def from_urlpath(cls, path, app=None):
        kls = cls.get_extension_class(path)
        if cls.generic:
            for kls in cls.playable_extension_classes:
                if kls.detect_extension(path):
                    return kls.from_urlpath(path, app=app)
        return super(PlayableExtension, cls).from_urlpath(path, app=app)

    @classmethod
    def register_playable_extension_class(cls, kls):
        cls.playable_extension_classes.append(kls)
        return kls


@PlayableExtension.register_playable_extension_class
class PlayableAudioFile(PlayableExtension, File):
    """Audio file node."""

    playable_extensions = {
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg',
        'wav': 'audio/wav',
        }


@PlayableExtension.register_playable_extension_class
class PLSFile(PlayableExtension, File):
    """PLS playlist file node."""

    playable_list = True
    playable_extensions = {
        'pls': 'audio/x-scpls',
        }

    ini_parser_class = PLSFileParser
    maxsize = getattr(sys, 'maxint', 0) or getattr(sys, 'maxsize', 0) or 2**32

    def _entries(self):
        parser = self.ini_parser_class(self.path)
        maxsize = parser.getint('playlist', 'NumberOfEntries', None)
        range = six.moves.range
        for i in range(1, self.maxsize if maxsize is None else maxsize + 1):
            path = parser.get('playlist', 'File%d' % i, None)
            if not path:
                if maxsize:
                    continue
                break
            path = self.normalize_playable_path(path)
            if not path:
                continue
            yield self.playable_class(
                path=path,
                app=self.app,
                duration=parser.getint(
                    'playlist', 'Length%d' % i,
                    None
                    ),
                title=parser.get(
                    'playlist',
                    'Title%d' % i,
                    None
                    ),
                )


@PlayableExtension.register_playable_extension_class
class M3UFile(PlayableExtension, File):
    """M3U playlist file node."""

    playable_list = True
    playable_extensions = {
        'm3u': 'audio/x-mpegurl',
        'm3u8': 'audio/x-mpegurl',
        }

    def _iter_lines(self):
        prefix = '#EXTM3U\n'
        encoding = 'utf-8' if self.path.endswith('.m3u8') else 'ascii'
        with codecs.open(
          self.path, 'r',
          encoding=encoding,
          errors=underscore_replace
          ) as f:
            if f.read(len(prefix)) != prefix:
                f.seek(0)
            for line in f:
                line = line.rstrip()
                if line:
                    yield line

    def _entries(self):
        data = {}
        for line in self._iter_lines():
            if line.startswith('#EXTINF:'):
                duration, title = line.split(',', 1)
                data['duration'] = None if duration == '-1' else int(duration)
                data['title'] = title
            if not line:
                continue
            path = self.normalize_playable_path(line)
            if path:
                yield self.playable_class(path=path, app=self.app, **data)
            data.clear()


@Playable.register_directory_class
class PlayListDirectory(Playable, Directory):
    """Playable directory node."""

    playable_list = True

    @cached_property
    def parent(self):
        """Get standard directory node."""
        return self.directory_class(self.path, app=self.app)

    def entries(self, sortkey=None, reverse=None):
        """Get playable directory entries."""
        for node in self.listdir(sortkey=sortkey, reverse=reverse):
            if (not node.is_directory) and node.is_playable:
                yield node

    @classmethod
    def playable_check(cls, node):
        """Detect if given node contains playable files."""
        super_check = super(PlayListDirectory, cls).playable_check
        return node.is_directory and any(
            super_check(child)
            for child in node._listdir()
            if not child.is_directory
            )


def detect_playable_mimetype(path):
    """Detect if path corresponds to a playable file by its extension."""
    return PlayableExtension.detect_mimetype(path)
