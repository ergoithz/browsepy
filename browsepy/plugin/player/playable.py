
import sys
import codecs
import os.path

from werkzeug.utils import cached_property
from browsepy.compat import range, PY_LEGACY
from browsepy.file import Node, File, Directory, \
                          underscore_replace, check_under_base


if PY_LEGACY:
    import ConfigParser as configparser
else:
    import configparser


extensions = {
    'mp3': 'audio/mpeg',
    'ogg': 'audio/ogg',
    'wav': 'audio/wav',
    'm3u': 'audio/x-mpegurl',
    'm3u8': 'audio/x-mpegurl',
    'pls': 'audio/x-scpls',
}


class PlayableFile(File):
    media_map = {
        'audio/mpeg': 'mp3',
        'audio/ogg': 'ogg',
        'audio/wav': 'wav',
    }
    mimetypes = tuple(media_map)

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


class PlayListFile(Directory):
    playable_class = PlayableFile
    mimetypes = ('audio/x-mpegurl', 'audio/x-scpls')

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
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(self.parent.path, path))
        if check_under_base(path, self.app.config['directory_base']):
            return path
        return None


class PLSFile(PlayListFile):
    ini_parser_cls = (
        configparser.SafeConfigParser
        if hasattr(configparser, 'SafeConfigParser') else
        configparser.ConfigParser
        )
    maxsize = getattr(sys, 'maxsize', None) or getattr(sys, 'maxint', None)
    mimetype = 'audio/x-scpls'

    @cached_property
    def _parser(self):
        parser = self.ini_parser()
        parser.read(self.path)
        return parser

    def _listdir(self):
        maxsize = self._parser.getint('playlist', 'NumberOfEntries', None)
        for i in range(self.maxsize if maxsize is None else maxsize):
            pf = self.playable_class(
                path=self.normalize_playable_path(
                    self._parser.get('playlist', 'File%d' % i, None)
                    ),
                duration=self._parser.getint('playlist', 'Length%d' % i, None),
                title=self._parser.get('playlist', 'Title%d' % i, None),
                )
            if pf.path:
                yield pf
            elif maxsize is None:
                break


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

    def _listdir(self):
        data = {}
        for line in self._iter_lines():
            if line.startswith('#EXTINF:'):
                duration, title = line.split(',', 1)
                data['duration'] = None if duration == '-1' else int(duration)
                data['title'] = title
                continue
            print(line)
            data['path'] = self.normalize_playable_path(line)
            if data['path']:
                yield self.playable_class(**data)
                data.clear()


class PlayableDirectory(Directory):
    @classmethod
    def detect(cls, node):
        if node.is_directory:
            for file in node._listdir():
                if file.name.rsplit('.', 1)[-1] in extensions:
                    return True
        return False

    def _listdir(self):
        for file in super(PlayableDirectory, self)._listdir():
            if file.name.rsplit('.', 1)[-1] in extensions:
                yield file
