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
from .compat import range, deprecated


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
    '''
    Abstract filesystem node class.

    This represents an unspecified entity with a filesystem's path suitable for
    being inherited by plugins.

    When inheriting, the following attributes should be overwritten in order
    to specify :meth:`from_urlpath` classmethod behavior:

    * :attr:`generic`, if true, an instance of directory_class or file_class
      will be created instead of an instance of this class tself.
    * :attr:`directory_class`, class will be used for directory nodes,
    * :attr:`file_class`, class will be used for file nodes.
    '''
    generic = True
    directory_class = None  # set later at import time
    file_class = None  # set later at import time

    re_charset = re.compile('; charset=(?P<charset>[^;]+)')
    can_download = False

    @cached_property
    def plugin_manager(self):
        '''
        Get current app's plugin manager.

        :returns: plugin manager instance
        '''
        return self.app.extensions['plugin_manager']

    @cached_property
    def widgets(self):
        '''
        List widgets with filter return True for this node (or without filter).

        Remove button is prepended if :property:can_remove returns true.

        :returns: list of widgets
        :rtype: list of namedtuple instances
        '''
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
        '''
        Get last widget with place "entry-link".

        :returns: widget on entry-link (ideally a link one)
        :rtype: namedtuple instance
        '''
        link = None
        for widget in self.widgets:
            if widget.place == 'entry-link':
                link = widget
        return link

    @cached_property
    def can_remove(self):
        '''
        Get if current node can be removed based on app config's
        directory_remove.

        :returns: True if current node can be removed, False otherwise.
        :rtype: bool
        '''
        dirbase = self.app.config["directory_remove"]
        return dirbase and self.path.startswith(dirbase + os.sep)

    @cached_property
    def stats(self):
        '''
        Get current stats object as returned by os.stat function.

        :returns: stats object
        :rtype: posix.stat_result or nt.stat_result
        '''
        return os.stat(self.path)

    @cached_property
    def parent(self):
        '''
        Get parent node if available based on app config's directory_base.

        :returns: parent object if available
        :rtype: Node instance or None
        '''
        if self.path == self.app.config['directory_base']:
            return None
        parent = os.path.dirname(self.path) if self.path else None
        return self.directory_class(parent, self.app) if parent else None

    @cached_property
    def ancestors(self):
        '''
        Get list of ancestors until app config's directory_base is reached.

        :returns: list of ancestors starting from nearest.
        :rtype: list of Node objects
        '''
        ancestors = []
        parent = self.parent
        while parent:
            ancestors.append(parent)
            parent = parent.parent
        return ancestors

    @property
    def modified(self):
        '''
        Get human-readable last modification date-time.

        :returns: iso9008-like date-time string (without timezone)
        :rtype: str
        '''
        dt = datetime.datetime.fromtimestamp(self.stats.st_mtime)
        return dt.strftime('%Y.%m.%d %H:%M:%S')

    @property
    def urlpath(self):
        '''
        Get the url substring corresponding to this node for those endpoints
        accepting a 'path' parameter, suitable for :meth:`from_urlpath`.

        :returns: relative-url-like for node's path
        :rtype: str
        '''
        return abspath_to_urlpath(self.path, self.app.config['directory_base'])

    @property
    def name(self):
        '''
        Get the basename portion of node's path.

        :returns: filename
        :rtype: str
        '''
        return os.path.basename(self.path)

    @property
    def type(self):
        '''
        Get the mime portion of node's mimetype (without the encoding part).

        :returns: mimetype
        :rtype: str
        '''
        return self.mimetype.split(";", 1)[0]

    @property
    def category(self):
        '''
        Get mimetype category (first portion of mimetype before the slash).

        :returns: mimetype category
        :rtype: str

        As of 2016-11-03's revision of RFC2046 it could be one of the
        following:
            * application
            * audio
            * example
            * image
            * message
            * model
            * multipart
            * text
            * video
        '''
        return self.type.split('/', 1)[0]

    def __init__(self, path=None, app=None, **defaults):
        '''
        :param path: local path
        :type path: str
        :param path: optional app instance
        :type path: flask.app
        :param **defaults: attributes will be set to object
        '''
        self.path = compat.fsdecode(path) if path else None
        self.app = current_app if app is None else app
        self.__dict__.update(defaults)  # only for attr and cached_property

    def remove(self):
        '''
        Does nothing except raising if can_remove property returns False.

        :raises: OutsideRemovableBase if :property:can_remove returns false
        '''
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
        '''
        Convenience method for setting current class file_class property.

        :param kls: class to set
        :type kls: type
        :returns: given class (enabling using this as decorator)
        :rtype: type
        '''
        cls.file_class = kls
        return kls

    @classmethod
    def register_directory_class(cls, kls):
        '''
        Convenience method for setting current class directory_class property.

        :param kls: class to set
        :type kls: type
        :returns: given class (enabling using this as decorator)
        :rtype: type
        '''
        cls.directory_class = kls
        return kls


@Node.register_file_class
class File(Node):
    '''
    Filesystem file class.

    Some notes:

    * :attr:`can_download` is fixed to True, so Files can be downloaded
      inconditionaly.
    * :attr:`can_upload` is fixed to False, so nothing can be uploaded to
      file path.
    * :attr:`is_directory` is fixed to False, so no further checks are
      performed.
    * :attr:`generic` is set to False, so static method :meth:`from_urlpath`
      will always return instances of this class.
    '''
    can_download = True
    can_upload = False
    is_directory = False
    generic = False

    @cached_property
    def widgets(self):
        '''
        List widgets with filter return True for this file (or without filter).

        Entry link is prepended.
        Download button is prepended if :property:can_download returns true.
        Remove button is prepended if :property:can_remove returns true.

        :returns: list of widgets
        :rtype: list of namedtuple instances
        '''
        widgets = [
            self.plugin_manager.create_widget(
                'entry-link',
                'link',
                file=self,
                endpoint='open'
                )
            ]
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

    @cached_property
    def mimetype(self):
        '''
        Get full mimetype, with encoding if available.

        :returns: mimetype
        :rtype: str
        '''
        return self.plugin_manager.get_mimetype(self.path)

    @cached_property
    def is_file(self):
        '''
        Get if node is file.

        :returns: True if file, False otherwise
        :rtype: bool
        '''
        return os.path.isfile(self.path)

    @property
    def size(self):
        '''
        Get human-readable node size in bytes.
        If directory, this will corresponds with own inode size.

        :returns: fuzzy size with unit
        :rtype: str
        '''
        size, unit = fmt_size(
            self.stats.st_size,
            self.app.config["use_binary_multiples"]
            )
        if unit == binary_units[0]:
            return "%d %s" % (size, unit)
        return "%.2f %s" % (size, unit)

    @property
    def encoding(self):
        '''
        Get encoding part of mimetype, or "default" if not available.

        :returns: file conding as returned by mimetype function or "default"
        :rtype: str
        '''
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
    '''
    Filesystem directory class.

    Some notes:

    * :attr:`mimetype` is fixed to 'inode/directory', so mimetype detection
      functions won't be called in this case.
    * :attr:`is_file` is fixed to False, so no further checks are needed.
    * :attr:`size` is fixed to 0 (zero), so stats are not required for this.
    * :attr:`encoding` is fixed to 'default'.
    * :attr:`generic` is set to False, so static method :meth:`from_urlpath`
      will always return instances of this class.
    '''
    _listdir_cache = None
    mimetype = 'inode/directory'
    is_file = False
    size = 0
    encoding = 'default'
    generic = False

    @cached_property
    def widgets(self):
        '''
        List widgets with filter return True for this dir (or without filter).

        Entry link is prepended.
        Upload scripts and widget are added if :property:can_upload is true.
        Download button is prepended if :property:can_download returns true.
        Remove button is prepended if :property:can_remove returns true.

        :returns: list of widgets
        :rtype: list of namedtuple instances
        '''
        widgets = [
            self.plugin_manager.create_widget(
                'entry-link',
                'link',
                file=self,
                endpoint='browse'
                )
            ]
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

    @cached_property
    def is_directory(self):
        '''
        Get if path points to a real directory.

        :returns: True if real directory, False otherwise
        :rtype: bool
        '''
        return os.path.isdir(self.path)

    @cached_property
    def can_download(self):
        '''
        Get if path is downloadable (if app's `directory_downloadable` config
        property is True).

        :returns: True if downloadable, False otherwise
        :rtype: bool
        '''
        return self.app.config['directory_downloadable']

    @cached_property
    def can_upload(self):
        '''
        Get if a file can be uploaded to path (if directory path is under app's
        `directory_upload` config property).

        :returns: True if a file can be upload to directory, False otherwise
        :rtype: bool
        '''
        dirbase = self.app.config["directory_upload"]
        return dirbase and (
            dirbase == self.path or
            self.path.startswith(dirbase + os.sep)
            )

    @cached_property
    def is_empty(self):
        '''
        Get if directory is empty (based on :meth:`_listdir`).

        :returns: True if this directory has no entries, False otherwise.
        :rtype: bool
        '''
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
        Get sorted list (by given sortkey and reverse params) of File objects.

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

    Note on corroutines: this class uses threading by default, but
    corroutine-based applications can change this behavior overriding the
    :attr:`event_class` and :attr:`thread_class` values.
    '''
    event_class = threading.Event
    thread_class = threading.Thread
    tarfile_class = tarfile.open

    def __init__(self, path, buffsize=10240):
        '''
        Internal tarfile object will be created, and compression will start
        on a thread until buffer became full with writes becoming locked until
        a read occurs.

        :param path: local path of directory whose content will be compressed.
        :type path: str
        :param buffsize: size of internal buffer on bytes, defaults to 10KiB
        :type buffsize: int
        '''
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
        '''
        Writes data on internal tarfile instance, which writes to current
        object, using :meth:`write`.

        As this method is blocking, it is used inside a thread.

        This method is called automatically, on a thread, on initialization,
        so there is little need to call it manually.
        '''
        self._tarfile.add(self.path, "")
        self._tarfile.close()  # force stream flush
        self._finished += 1
        if not self._result.is_set():
            self._result.set()

    def write(self, data):
        '''
        Write method used by internal tarfile instance to output data.
        This method blocks tarfile execution once internal buffer is full.

        As this method is blocking, it is used inside the same thread of
        :meth:`fill`.

        :param data: bytes to write to internal buffer
        :type data: bytes
        :returns: number of bytes written
        :rtype: int
        '''
        self._add.wait()
        self._data += data
        if len(self._data) > self._want:
            self._add.clear()
            self._result.set()
        return len(data)

    def read(self, want=0):
        '''
        Read method, gets data from internal buffer while releasing
        :meth:`write` locks when needed.

        The lock usage means it must ran on a different thread than
        :meth:`fill`, ie. the main thread, otherwise will deadlock.

        The combination of both write and this method running on different
        threads makes tarfile being streamed on-the-fly, with data chunks being
        processed and retrieved on demand.

        :param want: number bytes to read, defaults to 0 (all available)
        :type want: int
        :returns: tarfile data as bytes
        :rtype: bytes
        '''
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
        '''
        Iterate through tarfile result chunks.

        Similarly to :meth:`read`, this methos must ran on a different thread
        than :meth:`write` calls.

        :yields: data chunks as taken from :meth:`read`.
        :ytype: bytes
        '''
        data = self.read()
        while data:
            yield data
            data = self.read()


class OutsideDirectoryBase(Exception):
    '''
    Exception thrown when trying to access to a file outside path defined on
    `directory_base` config property.
    '''
    pass


class OutsideRemovableBase(Exception):
    '''
    Exception thrown when trying to access to a file outside path defined on
    `directory_remove` config property.
    '''
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


def secure_filename(path, destiny_os=os.name, fs_encoding=compat.FS_ENCODING):
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
