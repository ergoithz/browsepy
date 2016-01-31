
import sys
import codecs
import os.path

from flask._compat import with_metaclass
from werkzeug.utils import cached_property
from browsepy.compat import range, str_base, PY_LEGACY
from browsepy.file import File, undescore_replace, check_under_base


if PY_LEGACY:
    import ConfigParser as configparser
else:
    import configparser


mimetypes = {
    'mp3': 'audio/mpeg',
    'ogg': 'audio/ogg',
    'wav': 'audio/wav',
    'm3u': 'audio/x-mpegurl',
    'm3u8': 'audio/x-mpegurl',
    'pls': 'audio/x-scpls',
}


class PlayableFile(File):
    parent_class = File
    media_map = {
        'audio/mpeg': 'mp3',
        'audio/ogg': 'ogg',
        'audio/wav': 'wav',
    }

    def __init__(self, duration=None, title=None, **kwargs):
        self.duration = duration
        self.title = title
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


class MetaPlayListFile(type):
    def __init__(cls, name, bases, nmspc):
        '''
        Abstract-class mimetype-based implementation registration on nearest
        abstract parent.
        '''
        type.__init__(cls, name, bases, nmspc)
        if cls.abstract_class is None:
            cls.specific_classes = {}
            cls.abstract_class = cls
        elif isinstance(cls.mimetype, str_base):
            cls.abstract_class.specific_classes[cls.mimetype] = cls


class PlayListFile(with_metaclass(MetaPlayListFile, File)):
    abstract_class = None
    playable_class = PlayableFile

    def __new__(cls, *args, **kwargs):
        '''
        Polimorfic mimetype-based constructor
        '''
        self = super(PlayListFile, cls).__new__(cls)
        if cls is cls.abstract_class:
            self.__init__(*args, **kwargs)
            if self.mimetype in cls.abstract_class.specific_classes:
                return cls.specific_classes[self.mimetype](*args, **kwargs)
        return self

    def iter_files(self):
        if False:
            yield

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

    def iter_files(self):
        maxsize = self._parser.getint('playlist', 'NumberOfEntries', None)
        for i in range(self.maxsize if maxsize is None else maxsize):
            pf = self.playable_class(
                path = self.normalize_playable_path(
                    self._parser.get('playlist', 'File%d' % i, None)
                    ),
                duration = self._parser.getint('playlist', 'Length%d' % i, None),
                title =  self._parser.get('playlist', 'Title%d' % i, None),
                )
            if pf.path:
                yield pf
            elif maxsize is None:
                break


class M3UFile(PlayListFile):
    mimetype = 'audio/x-mpegurl'

    def _extract_line(self, line, file=None):
        if line.startswith('#EXTINF:'):
            duration, title = line.split(',', 1)
            file.duration = None if duration == '-1' else int(duration)
            file.title = title
            return False
        file.path = self.normalize_playable_path(line)
        return not file.path is None

    def iter_files(self):
        prefix = '#EXTM3U\n'
        encoding = 'utf-8' if self.path.endswith('.m3u8') else 'ascii'
        with codecs.open(self.path, 'r', encoding=encoding, errors=undescore_replace) as f:
            if f.read(len(prefix)) == prefix:
                pf = PlayableFile()
                for line in f:
                    line = line.rstrip('\n', 1)
                    if line and self._extract_line(line, pf):
                        yield pf
                        pf = PlayableFile()
