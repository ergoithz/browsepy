
import sys
import codecs
import os.path
import warnings

from browsepy.compat import range, PY_LEGACY  # noqa
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
        with warnings.catch_warnings():
            # We already know about SafeConfigParser deprecation!
            warnings.filterwarnings('ignore', category=DeprecationWarning)
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


class PlayableBase(File):
    extensions = {
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg',
        'wav': 'audio/wav',
        'm3u': 'audio/x-mpegurl',
        'm3u8': 'audio/x-mpegurl',
        'pls': 'audio/x-scpls',
    }

    @classmethod
    def extensions_from_mimetypes(cls, mimetypes):
        mimetypes = frozenset(mimetypes)
        return {
            ext: mimetype
            for ext, mimetype in cls.extensions.items()
            if mimetype in mimetypes
        }

    @classmethod
    def detect(cls, node, os_sep=os.sep):
        basename = node.path.rsplit(os_sep)[-1]
        if '.' in basename:
            ext = basename.rsplit('.')[-1]
            return cls.extensions.get(ext, None)
        return None


class PlayableFile(PlayableBase):
    mimetypes = ['audio/mpeg', 'audio/ogg', 'audio/wav']
    extensions = PlayableBase.extensions_from_mimetypes(mimetypes)
    media_map = {mime: ext for ext, mime in extensions.items()}

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


class PlayListFile(PlayableBase):
    playable_class = PlayableFile
    mimetypes = ['audio/x-mpegurl', 'audio/x-mpegurl', 'audio/x-scpls']
    extensions = PlayableBase.extensions_from_mimetypes(mimetypes)

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
        path = os.path.normpath(path)
        if not os.path.isabs(path):
            return os.path.join(self.parent.path, path)
        drive = os.path.splitdrive(self.path)[0]
        if drive and not os.path.splitdrive(path)[0]:
            path = drive + path
        if check_under_base(path, self.app.config['directory_base']):
            return path
        return None

    def _entries(self):
        return
        yield  # noqa

    def entries(self):
        for file in self._entries():
            if PlayableFile.detect(file):
                yield file


class PLSFile(PlayListFile):
    ini_parser_class = PLSFileParser
    maxsize = getattr(sys, 'maxint', 0) or getattr(sys, 'maxsize', 0) or 2**32
    mimetype = 'audio/x-scpls'
    extensions = PlayableBase.extensions_from_mimetypes([mimetype])

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
    extensions = PlayableBase.extensions_from_mimetypes([mimetype])

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


class PlayableDirectory(Directory):
    file_class = PlayableFile
    name = ''

    @property
    def parent(self):
        return super(PlayableDirectory, self)  # parent is self as directory

    @classmethod
    def detect(cls, node):
        if node.is_directory:
            for file in node._listdir():
                if PlayableFile.detect(file):
                    return cls.mimetype
        return None

    def entries(self):
        for file in super(PlayableDirectory, self)._listdir():
            if PlayableFile.detect(file):
                yield file


def detect_playable_mimetype(path, os_sep=os.sep):
    basename = path.rsplit(os_sep)[-1]
    if '.' in basename:
        ext = basename.rsplit('.')[-1]
        return PlayableBase.extensions.get(ext, None)
    return None
