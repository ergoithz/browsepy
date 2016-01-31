#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
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
import functools

from flask import current_app, send_from_directory, Response
from werkzeug.utils import cached_property

from .compat import PY_LEGACY, range

undescore_replace = '%s:underscore' % __name__
codecs.register_error(undescore_replace,
                      (lambda error: (u'_', error.start + 1))
                      if PY_LEGACY else
                      (lambda error: ('_', error.start + 1))
                      )
if not PY_LEGACY:
    unicode = str


class File(object):
    re_charset = re.compile('; charset=(?P<charset>[^;]+)')
    parent_class = None # none means current class

    def __init__(self, path=None, app=None):
        self.path = path
        self.app = current_app if app is None else app

    def remove(self):
        if not self.can_remove:
            raise OutsideRemovableBase("File outside removable base")
        if self.is_directory:
            shutil.rmtree(self.path)
        else:
            os.unlink(self.path)

    def download(self):
        if self.is_directory:
            stream = TarFileStream(
                self.path,
                self.app.config["directory_tar_buffsize"]
                )
            return Response(stream, mimetype="application/octet-stream")
        directory, name = os.path.split(self.path)
        return send_from_directory(directory, name, as_attachment=True)

    def contains(self, filename):
        return os.path.exists(os.path.join(self.path, filename))

    def choose_filename(self, filename, attempts=999):
        new_filename = filename
        for attempt in range(2, attempts+1):
            if not self.contains(new_filename):
                return new_filename
            new_filename = alternative_filename(filename, attempt)
        while self.contains(new_filename):
            new_filename = alternative_filename(filename)
        return new_filename

    @property
    def plugin_manager(self):
        return self.app.extensions['plugin_manager']

    @property
    def default_action(self):
        for action in self.actions:
            if action.widget.place == 'link':
                return action
        endpoint = 'browse' if self.is_directory else 'open'
        widget = self.plugin_manager.link_class.from_file(self)
        return self.plugin_manager.action_class(endpoint, widget)

    @cached_property
    def actions(self):
        return self.plugin_manager.get_actions(self)

    @cached_property
    def can_download(self):
        return self.app.config['directory_downloadable'] or not self.is_directory

    @cached_property
    def can_remove(self):
        dirbase = self.app.config["directory_remove"]
        if dirbase:
            return self.path.startswith(dirbase + os.sep)
        return False

    @cached_property
    def can_upload(self):
        dirbase = self.app.config["directory_upload"]
        if self.is_directory and dirbase:
            return dirbase == self.path or self.path.startswith(dirbase + os.sep)
        return False

    @cached_property
    def stats(self):
        return os.stat(self.path)

    @cached_property
    def mimetype(self):
        if self.is_directory:
            return 'inode/directory'
        return self.plugin_manager.get_mimetype(self.path)

    @cached_property
    def is_directory(self):
        return os.path.isdir(self.path)

    @cached_property
    def is_file(self):
        return os.path.isfile(self.path)

    @cached_property
    def is_empty(self):
        return not self.raw_listdir

    @cached_property
    def parent(self):
        if self.path == self.app.config['directory_base']:
            return None
        parent_class = self.parent_class or self.__class__
        return parent_class(os.path.dirname(self.path), self.app)

    @cached_property
    def ancestors(self):
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        return tuple(ancestors)

    @cached_property
    def raw_listdir(self):
        return os.listdir(self.path)

    @property
    def modified(self):
        return datetime.datetime.fromtimestamp(self.stats.st_mtime).strftime('%Y.%m.%d %H:%M:%S')

    @property
    def size(self):
        size, unit = fmt_size(self.stats.st_size, self.app.config["use_binary_multiples"])
        if unit == binary_units[0]:
            return "%d %s" % (size, unit)
        return "%.2f %s" % (size, unit)

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
    def encoding(self):
        if ";" in self.mimetype:
            match = self.re_charset.search(self.mimetype)
            gdict = match.groupdict() if match else {}
            return gdict.get("charset") or "default"
        return "default"

    def listdir(self):
        path_joiner = functools.partial(os.path.join, self.path)
        content = [
            self.__class__(path=path_joiner(path), app=self.app)
            for path in self.raw_listdir
            ]
        content.sort(key=lambda f: (f.is_directory, f.name.lower()))
        return content

    @classmethod
    def from_urlpath(cls, path, app=None):
        app = app or current_app
        base = app.config['directory_base']
        return cls(path=urlpath_to_abspath(path, base), app=app)


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
        self._tarfile = self.tarfile_class(fileobj=self, mode="w|gz", bufsize=buffsize) # stream write
        self._th = self.thread_class(target=self.fill)
        self._th.start()

    def fill(self):
        self._tarfile.add(self.path, "")
        self._tarfile.close() # force stream flush
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


binary_units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
standard_units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
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

common_path_separators = '\\/'
def generic_filename(path):
    '''
    Extract filename of given path os-indepently, taking care of known path separators.

    :param path: path
    :return: filename
    :rtype: str or unicode (depending on given path)
    '''

    for sep in common_path_separators:
        if sep in path:
            _, path = path.rsplit(sep, 1)
    return path

restricted_chars = '\\/\0'
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

restricted_names = ('.', '..', '::', os.sep)
nt_device_names = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1', 'LPT2', 'LPT3', 'PRN', 'NUL')
fs_encoding = 'unicode' if os.name == 'nt' else sys.getfilesystemencoding() or 'ascii'
def check_forbidden_filename(filename, destiny_os=os.name, fs_encoding=fs_encoding,
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

def secure_filename(path, destiny_os=os.name, fs_encoding=fs_encoding):
    '''
    Get rid of parent path components and special filenames.

    If path is invalid or protected, return empty string.

    :param path: unsafe path
    :param destiny_os: destination operative system
    :param fs_encoding: destination filesystem filename encoding
    :return: filename or empty string
    :rtype: str or unicode (depending on python version, destiny_os and fs_encoding)
    '''
    path = generic_filename(path)
    path = clean_restricted_chars(path)

    if check_forbidden_filename(path, destiny_os=destiny_os, fs_encoding=fs_encoding):
        return ''

    if fs_encoding != 'unicode':
        if PY_LEGACY and not isinstance(path, unicode):
            path = unicode(path, encoding='latin-1')
        path = path.encode(fs_encoding, errors=undescore_replace).decode(fs_encoding)

    return path

fs_safe_characters = string.ascii_uppercase + string.digits
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
    filename_parts = filename.rsplit('.', 2)
    name = filename_parts[0]
    ext = ''.join('.%s' % ext for ext in filename_parts[1:])
    if attempt is None:
        extra = ' %s' % ''.join(random.choice(fs_safe_characters) for i in range(8))
    else:
        extra = ' (%d)' % attempt
    return '%s%s%s' % (name, extra, ext)
