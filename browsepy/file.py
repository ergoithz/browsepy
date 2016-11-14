#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import re
import shutil
import codecs
import threading
import string
import tarfile
import random
import datetime
import logging

from flask import current_app, send_from_directory
from werkzeug.utils import cached_property

from . import compat
from .compat import range


logger = logging.getLogger(__name__)
unicode_underscore = '_'.decode('utf-8') if compat.PY_LEGACY else '_'
underscore_replace = '%s:underscore' % __name__
codecs.register_error(underscore_replace,
                      lambda error: (unicode_underscore, error.start + 1)
                      )
binary_units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
standard_units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
common_path_separators = '\\/'
restricted_chars = '\\/\0'
restricted_names = ('.', '..', '::', os.sep)
nt_device_names = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1',
                   'LPT2', 'LPT3', 'PRN', 'NUL')
fs_safe_characters = string.ascii_uppercase + string.digits


class Node(object):
    generic = True
    directory_class = None  # set later at import time
    file_class = None  # set later at import time

    re_charset = re.compile('; charset=(?P<charset>[^;]+)')
    can_download = False

    @property
    def plugin_manager(self):
        return self.app.extensions['plugin_manager']

    @cached_property
    def widgets(self):
        widgets = []
        if self.can_remove:
            widgets.append(
                self.plugin_manager.create_widget(
                    'entry-actions',
                    'button',
                    file=self,
                    css='remove',
                    endpoint='remove'
                    )
                )
        return widgets + self.plugin_manager.get_widgets(file=self)

    @cached_property
    def link(self):
        for widget in self.widgets:
            if widget.place == 'entry-link':
                return widget

    @cached_property
    def can_remove(self):
        dirbase = self.app.config["directory_remove"]
        return dirbase and self.path.startswith(dirbase + os.sep)

    @cached_property
    def stats(self):
        return os.stat(self.path)

    @cached_property
    def parent(self):
        if self.path == self.app.config['directory_base']:
            return None
        parent = os.path.dirname(self.path) if self.path else None
        return self.directory_class(parent, self.app) if parent else None

    @cached_property
    def ancestors(self):
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        return ancestors

    @property
    def modified(self):
        dt = datetime.datetime.fromtimestamp(self.stats.st_mtime)
        return dt.strftime('%Y.%m.%d %H:%M:%S')

    @property
    def urlpath(self):
        return abspath_to_urlpath(self.path, self.app.config['directory_base'])

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def type(self):
        return self.mimetype.split(";", 1)[0]

    @property
    def category(self):
        return self.type.split('/', 1)[0]

    def __init__(self, path=None, app=None, **defaults):
        self.path = compat.fsdecode(path) if path else None
        self.app = current_app if app is None else app
        self.__dict__.update(defaults)

    def remove(self):
        if not self.can_remove:
            raise OutsideRemovableBase("File outside removable base")

    @classmethod
    def from_urlpath(cls, path, app=None):
        '''
        Alternative constructor which accepts a path as taken from URL and uses
        the given app or the current app config to get the real path.

        If class has attribute `generic` set to True, `directory_class` or
        `file_class` will be used as type.

        :param path: relative path as from URL
        :param app: optional, flask application
        :return: file object pointing to path
        :rtype: File
        '''
        app = app or current_app
        base = app.config['directory_base']
        path = urlpath_to_abspath(path, base)
        if not cls.generic:
            kls = cls
        elif os.path.isdir(path):
            kls = cls.directory_class
        else:
            kls = cls.file_class
        return kls(path=path, app=app)

    @classmethod
    def register_file_class(cls, kls):
        cls.file_class = kls
        return kls

    @classmethod
    def register_directory_class(cls, kls):
        cls.directory_class = kls
        return kls


@Node.register_file_class
class File(Node):
    can_download = True
    can_upload = False
    is_directory = False
    generic = False

    @cached_property
    def widgets(self):
        widgets = []
        if self.can_download:
            widgets.append(
                self.plugin_manager.create_widget(
                    'entry-actions',
                    'button',
                    file=self,
                    css='download',
                    endpoint='download_file'
                    )
                )
        return widgets + super(File, self).widgets

    @property
    def link(self):
        widget = super(File, self).link
        if widget is None:
            return self.plugin_manager.create_widget(
                'entry-link',
                'link',
                file=self,
                endpoint='open'
                )
        return widget

    @cached_property
    def mimetype(self):
        return self.plugin_manager.get_mimetype(self.path)

    @cached_property
    def is_file(self):
        return os.path.isfile(self.path)

    @property
    def size(self):
        size, unit = fmt_size(
            self.stats.st_size,
            self.app.config["use_binary_multiples"]
            )
        if unit == binary_units[0]:
            return "%d %s" % (size, unit)
        return "%.2f %s" % (size, unit)

    @property
    def encoding(self):
        if ";" in self.mimetype:
            match = self.re_charset.search(self.mimetype)
            gdict = match.groupdict() if match else {}
            return gdict.get("charset") or "default"
        return "default"

    def remove(self):
        '''
        Remove file.
        :raises OutsideRemovableBase: when not under removable base directory
        '''
        super(File, self).remove()
        os.unlink(self.path)

    def download(self):
        '''
        Get a Flask's send_file Response object pointing to this file.

        :returns: Response object as returned by flask's send_file
        :rtype: flask.Response
        '''
        directory, name = os.path.split(self.path)
        return send_from_directory(directory, name, as_attachment=True)


@Node.register_directory_class
class Directory(Node):
    _listdir_cache = None
    mimetype = 'inode/directory'
    is_file = False
    size = 0
    encoding = 'default'
    generic = False

    @cached_property
    def widgets(self):
        widgets = []
        if self.can_upload:
            widgets.extend((
                self.plugin_manager.create_widget(
                    'head',
                    'script',
                    file=self,
                    endpoint='static',
                    filename='browse.directory.head.js'
                ),
                self.plugin_manager.create_widget(
                    'scripts',
                    'script',
                    file=self,
                    endpoint='static',
                    filename='browse.directory.body.js'
                ),
                self.plugin_manager.create_widget(
                    'header',
                    'upload',
                    file=self,
                    text='Upload',
                    endpoint='upload'
                    )
                ))
        if self.can_download:
            widgets.append(
                self.plugin_manager.create_widget(
                    'entry-actions',
                    'button',
                    file=self,
                    css='download',
                    endpoint='download_directory'
                    )
                )
        return widgets + super(Directory, self).widgets

    @property
    def link(self):
        widget = super(Directory, self).link
        if widget is None:
            return self.plugin_manager.create_widget(
                'entry-link',
                'link',
                file=self,
                endpoint='browse'
                )
        return widget

    @cached_property
    def is_directory(self):
        return os.path.isdir(self.path)

    @cached_property
    def can_download(self):
        return self.app.config['directory_downloadable']

    @cached_property
    def can_upload(self):
        dirbase = self.app.config["directory_upload"]
        return dirbase and (
            dirbase == self.path or
            self.path.startswith(dirbase + os.sep)
            )

    @cached_property
    def is_empty(self):
        if self._listdir_cache is not None:
            return bool(self._listdir_cache)
        for entry in self._listdir():
            return False
        return True

    def remove(self):
        '''
        Remove directory tree.

        :raises OutsideRemovableBase: when not under removable base directory
        '''
        super(Directory, self).remove()
        shutil.rmtree(self.path)

    def download(self):
        '''
        Get a Flask Response object streaming a tarball of this directory.

        :returns: Response object
        :rtype: flask.Response
        '''
        return self.app.response_class(
            TarFileStream(
                self.path,
                self.app.config["directory_tar_buffsize"]
                ),
            mimetype="application/octet-stream"
            )

    def contains(self, filename):
        '''
        Check if directory contains an entry with given filename.

        :param filename: filename will be check
        :type filename: str
        :returns: True if exists, False otherwise.
        :rtype: bool
        '''
        return os.path.exists(os.path.join(self.path, filename))

    def choose_filename(self, filename, attempts=999):
        '''
        Get a new filename which does not colide with any entry on directory,
        based on given filename.

        :param filename: base filename
        :type filename: str
        :param attempts: number of attempts, defaults to 999
        :type attempts: int
        :returns: filename
        :rtype: str
        '''
        new_filename = filename
        for attempt in range(2, attempts + 1):
            if not self.contains(new_filename):
                return new_filename
            new_filename = alternative_filename(filename, attempt)
        while self.contains(new_filename):
            new_filename = alternative_filename(filename)
        return new_filename

    def _listdir(self):
        '''
        Iter unsorted entries on this directory.

        :yields: Directory or File instance for each entry in directory
        :ytype: Node
        '''
        precomputed_stats = os.name == 'nt'
        for entry in compat.scandir(self.path):
            kwargs = {'path': entry.path, 'app': self.app, 'parent': self}
            if precomputed_stats and not entry.is_symlink():
                kwargs['stats'] = entry.stats()
            if entry.is_dir(follow_symlinks=True):
                yield self.directory_class(**kwargs)
                continue
            yield self.file_class(**kwargs)

    def listdir(self, sortkey=None, reverse=False):
        '''
        Get sorted list (by `is_directory` and `name` properties) of File
        objects.

        :return: sorted list of File instances
        :rtype: list of File
        '''
        if self._listdir_cache is None:
            if sortkey:
                data = sorted(self._listdir(), key=sortkey, reverse=reverse)
            elif reverse:
                data = list(reversed(self._listdir()))
            else:
                data = list(self._listdir())
            self._listdir_cache = data
        return self._listdir_cache


class TarFileStream(object):
    '''
    Tarfile which compresses while reading for streaming.

    Buffsize can be provided, it must be 512 multiple (the tar block size) for
    compression.
    '''
    event_class = threading.Event
    thread_class = threading.Thread
    tarfile_class = tarfile.open

    def __init__(self, path, buffsize=10240):
        self.path = path
        self.name = os.path.basename(path) + ".tgz"

        self._finished = 0
        self._want = 0
        self._data = bytes()
        self._add = self.event_class()
        self._result = self.event_class()
        self._tarfile = self.tarfile_class(  # stream write
            fileobj=self,
            mode="w|gz",
            bufsize=buffsize
            )
        self._th = self.thread_class(target=self.fill)
        self._th.start()

    def fill(self):
        self._tarfile.add(self.path, "")
        self._tarfile.close()  # force stream flush
        self._finished += 1
        if not self._result.is_set():
            self._result.set()

    def write(self, data):
        self._add.wait()
        self._data += data
        if len(self._data) > self._want:
            self._add.clear()
            self._result.set()
        return len(data)

    def read(self, want=0):
        if self._finished:
            if self._finished == 1:
                self._finished += 1
                return ""
            return EOFError("EOF reached")

        # Thread communication
        self._want = want
        self._add.set()
        self._result.wait()
        self._result.clear()

        if want:
            data = self._data[:want]
            self._data = self._data[want:]
        else:
            data = self._data
            self._data = bytes()
        return data

    def __iter__(self):
        data = self.read()
        while data:
            yield data
            data = self.read()


class OutsideDirectoryBase(Exception):
    pass


class OutsideRemovableBase(Exception):
    pass


def fmt_size(size, binary=True):
    '''
    Get size and unit.

    :param size: size in bytes
    :param binary: whether use binary or standard units, defaults to True
    :return: size and unit
    :rtype: tuple of int and unit as str
    '''
    if binary:
        fmt_sizes = binary_units
        fmt_divider = 1024.
    else:
        fmt_sizes = standard_units
        fmt_divider = 1000.
    for fmt in fmt_sizes[:-1]:
        if size < 1000:
            return (size, fmt)
        size /= fmt_divider
    return size, fmt_sizes[-1]


def relativize_path(path, base, os_sep=os.sep):
    '''
    Make absolute path relative to an absolute base.

    :param path: absolute path
    :param base: absolute base path
    :param os_sep: path component separator, defaults to current OS separator
    :return: relative path
    :rtype: str or unicode
    :raises OutsideDirectoryBase: if path is not below base
    '''
    if not check_under_base(path, base, os_sep):
        raise OutsideDirectoryBase("%r is not under %r" % (path, base))
    prefix_len = len(base)
    if not base.endswith(os_sep):
        prefix_len += len(os_sep)
    return path[prefix_len:]


def abspath_to_urlpath(path, base, os_sep=os.sep):
    '''
    Make filesystem absolute path uri relative using given absolute base path.

    :param path: absolute path
    :param base: absolute base path
    :param os_sep: path component separator, defaults to current OS separator
    :return: relative uri
    :rtype: str or unicode
    :raises OutsideDirectoryBase: if resulting path is not below base
    '''
    return relativize_path(path, base, os_sep).replace(os_sep, '/')


def urlpath_to_abspath(path, base, os_sep=os.sep):
    '''
    Make uri relative path fs absolute using a given absolute base path.

    :param path: relative path
    :param base: absolute base path
    :param os_sep: path component separator, defaults to current OS separator
    :return: absolute path
    :rtype: str or unicode
    :raises OutsideDirectoryBase: if resulting path is not below base
    '''
    prefix = base if base.endswith(os_sep) else base + os_sep
    realpath = os.path.abspath(prefix + path.replace('/', os_sep))
    if base == realpath or realpath.startswith(prefix):
        return realpath
    raise OutsideDirectoryBase("%r is not under %r" % (realpath, base))


def generic_filename(path):
    '''
    Extract filename of given path os-indepently, taking care of known path
    separators.

    :param path: path
    :return: filename
    :rtype: str or unicode (depending on given path)
    '''

    for sep in common_path_separators:
        if sep in path:
            _, path = path.rsplit(sep, 1)
    return path


def clean_restricted_chars(path, restricted_chars=restricted_chars):
    '''
    Get path without restricted characters.

    :param path: path
    :return: path without restricted characters
    :rtype: str or unicode (depending on given path)
    '''
    for character in restricted_chars:
        path = path.replace(character, '_')
    return path


def check_forbidden_filename(filename,
                             destiny_os=os.name,
                             restricted_names=restricted_names):
    '''
    Get if given filename is forbidden for current OS or filesystem.

    :param filename:
    :param destiny_os: destination operative system
    :param fs_encoding: destination filesystem filename encoding
    :return: wether is forbidden on given OS (or filesystem) or not
    :rtype: bool
    '''
    if destiny_os == 'nt':
        fpc = filename.split('.', 1)[0].upper()
        if fpc in nt_device_names:
            return True

    return filename in restricted_names


def check_under_base(path, base, os_sep=os.sep):
    '''
    Check if given absolute path is under given base.

    :param path: absolute path
    :param base: absolute base path
    :return: wether file is under given base or not
    :rtype: bool
    '''
    prefix = base if base.endswith(os_sep) else base + os_sep
    return path == base or path.startswith(prefix)


def secure_filename(path, destiny_os=os.name, fs_encoding=compat.fs_encoding):
    '''
    Get rid of parent path components and special filenames.

    If path is invalid or protected, return empty string.

    :param path: unsafe path
    :type: str
    :param destiny_os: destination operative system
    :type destiny_os: str
    :return: filename or empty string
    :rtype: str
    '''
    path = generic_filename(path)
    path = clean_restricted_chars(path)

    if check_forbidden_filename(path, destiny_os=destiny_os):
        return ''

    if isinstance(path, bytes):
        path = path.decode('latin-1', errors=underscore_replace)

    # Decode and recover from filesystem encoding in order to strip unwanted
    # characters out
    kwargs = dict(
        os_name=destiny_os,
        fs_encoding=fs_encoding,
        errors=underscore_replace
        )
    fs_encoded_path = compat.fsencode(path, **kwargs)
    fs_decoded_path = compat.fsdecode(fs_encoded_path, **kwargs)
    return fs_decoded_path


def alternative_filename(filename, attempt=None):
    '''
    Generates an alternative version of given filename.

    If an number attempt parameter is given, will be used on the alternative
    name, a random value will be used otherwise.

    :param filename: original filename
    :param attempt: optional attempt number, defaults to null
    :return: new filename
    :rtype: str or unicode
    '''
    filename_parts = filename.rsplit(u'.', 2)
    name = filename_parts[0]
    ext = ''.join(u'.%s' % ext for ext in filename_parts[1:])
    if attempt is None:
        choose = random.choice
        extra = u' %s' % ''.join(choose(fs_safe_characters) for i in range(8))
    else:
        extra = u' (%d)' % attempt
    return u'%s%s%s' % (name, extra, ext)
