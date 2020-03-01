
import sys
import codecs
import os.path
import warnings

from werkzeug.utils import cached_property

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


class ImageBase(File):
    extensions = {
        'png': 'image/png',
        'jpg': 'image/jpg',
        'gif': 'image/gif'
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
            ext = basename.rsplit('.')[-1].lower().strip()
            return cls.extensions.get(ext, None)
        return None


class ImageFile(ImageBase):
    mimetypes = ['image/png', 'image/jpg', 'image/gif']
    extensions = ImageBase.extensions_from_mimetypes(mimetypes)
    media_map = {mime: ext for ext, mime in extensions.items()}

    def __init__(self, path, **kwargs):
        super(ImageFile, self).__init__(path=path, **kwargs)
        #TODO: read exif
        self.title = os.path.basename(path)

    @property
    def title(self):
        return self._title or self.name

    @title.setter
    def title(self, title):
        self._title = title

    @property
    def media_format(self):
        return self.media_map[self.type]


class ImageDirectory(Directory):
    file_class = ImageFile
    name = ''

    @cached_property
    def parent(self):
        return Directory(self.path)

    @classmethod
    def detect(cls, node):
        if node.is_directory:
            for file in node._listdir():
                if ImageFile.detect(file):
                    return cls.mimetype
        return None

    def entries(self, sortkey=None, reverse=None):
        listdir_fnc = super(ImageDirectory, self).listdir
        for file in listdir_fnc(sortkey=sortkey, reverse=reverse):
            if ImageFile.detect(file):
                yield file


def detect_image_mimetype(path, os_sep=os.sep):
    basename = path.rsplit(os_sep)[-1]
    if '.' in basename:
        ext = basename.rsplit('.')[-1]
        return ImageBase.extensions.get(ext, None)
    return None
