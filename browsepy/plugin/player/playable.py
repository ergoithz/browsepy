
import sys
import codecs
import os.path

from browsepy.compat import range, PY_LEGACY
from browsepy.file import Node, File, Directory, \
                          underscore_replace, check_under_base


if PY_LEGACY:
    import ConfigParser as configparser
else:
    import configparser

ConfigParserBase = (
    configparser.SafeConfigParser
    if hasattr(configparser, 'SafeConfigParser') else
    configparser.ConfigParser
    )


class PLSFileParser(object):
    '''
    ConfigParser wrapper accepting fallback on get for convenience.

    This wraps instead of inheriting due ConfigParse being classobj on python2.
    '''
    NOT_SET = type('NotSetType', (object,), {})
    parser_class = (
        configparser.SafeConfigParser
        if hasattr(configparser, 'SafeConfigParser') else
        configparser.ConfigParser
        )

    def __init__(self, path):
        self._parser = self.parser_class()
        self._parser.read(path)

    def getint(self, section, key, fallback=NOT_SET):
        try:
            return self._parser.getint(section, key)
        except (configparser.NoOptionError, ValueError):
            if fallback is self.NOT_SET:
                raise
            return fallback

    def get(self, section, key, fallback=NOT_SET):
        try:
            return self._parser.get(section, key)
        except (configparser.NoOptionError, ValueError):
            if fallback is self.NOT_SET:
                raise
            return fallback


class PlayableFile(File):
    media_map = {
        'audio/mpeg': 'mp3',
        'audio/ogg': 'ogg',
        'audio/wav': 'wav'
    }
    extensions = {
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg',
        'wav': 'audio/wav',
    }
    mimetypes = tuple(frozenset(extensions.values()))

    def __init__(self, **kwargs):
        self.duration = kwargs.pop('duration', None)
        self.title = kwargs.pop('title', None)
        super(PlayableFile, self).__init__(**kwargs)

    @property
    def title(self):
        return self._title or self.name

    @title.setter
    def title(self, title):
        self._title = title

    @property
    def media_format(self):
        return self.media_map[self.type]


class PlayListFile(File):
    playable_class = PlayableFile
    extensions = {
        'm3u': 'audio/x-mpegurl',
        'm3u8': 'audio/x-mpegurl',
        'pls': 'audio/x-scpls',
    }
    mimetypes = tuple(frozenset(extensions.values()))

    @classmethod
    def from_urlpath(cls, path, app=None):
        original = Node.from_urlpath(path, app)
        if original.mimetype == PlayableDirectory.mimetype:
            return PlayableDirectory(original.path, original.app)
        elif original.mimetype == M3UFile.mimetype:
            return M3UFile(original.path, original.app)
        if original.mimetype == PLSFile.mimetype:
            return PLSFile(original.path, original.app)
        return original

    def normalize_playable_path(self, path):
        if '://' in path:
            return path
        if not os.path.isabs(path):
            return os.path.normpath(os.path.join(self.parent.path, path))
        if check_under_base(path, self.app.config['directory_base']):
            return os.path.normpath(path)
        return None

    def _entries(self):
        return
        yield

    def entries(self):
        for file in self._entries():
            if detect_audio_mimetype(file.path):
                yield file


class PLSFile(PlayListFile):
    ini_parser_class = PLSFileParser
    maxsize = getattr(sys, 'maxsize', None) or getattr(sys, 'maxint', None)
    mimetype = 'audio/x-scpls'

    def _entries(self):
        parser = self.ini_parser_class(self.path)
        maxsize = parser.getint('playlist', 'NumberOfEntries', None)
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


class M3UFile(PlayListFile):
    mimetype = 'audio/x-mpegurl'

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
                line = line.rstrip('\n')
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


class PlayableDirectory(Directory):
    file_class = PlayableFile

    @classmethod
    def detect(cls, node):
        if node.is_directory:
            for file in node._listdir():
                if detect_audio_mimetype(file.path):
                    return True
        return False

    def entries(self):
        for file in super(PlayableDirectory, self)._listdir():
            if detect_audio_mimetype(file.path):
                yield file


def detect_playable_mimetype(path, os_sep=os.sep):
    return (
        detect_audio_mimetype(path, os_sep) or
        detect_playlist_mimetype(path, os_sep)
        )


def detect_audio_mimetype(path, os_sep=os.sep):
    basename = path.rsplit(os_sep)[-1]
    if '.' in basename:
        ext = basename.rsplit('.')[-1]
        return PlayableFile.extensions.get(ext, None)
    return None


def detect_playlist_mimetype(path, os_sep=os.sep):
    basename = path.rsplit(os_sep)[-1]
    if '.' in basename:
        ext = basename.rsplit('.')[-1]
        return PlayListFile.extensions.get(ext, None)
    return None
