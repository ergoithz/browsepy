
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
import subprocess
import mimetypes
import datetime

from flask import current_app, send_from_directory, Response
from werkzeug.utils import cached_property

from .compat import PY_LEGACY, range, FileNotFoundError

undescore_replace = '%s:underscore' % __name__
codecs.register_error(undescore_replace,
                      (lambda error: (u'_', error.start + 1))
                      if PY_LEGACY else
                      (lambda error: ('_', error.start + 1))
                      )

class File(object):
    re_mime_validate = re.compile('\w+/\w+(; \w+=[^;]+)*')
    re_charset = re.compile('; charset=(?P<charset>[^;]+)')
    def __init__(self, path, app=None):
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
    def actions(self):
        return self.app.actions.get(self.mimetype)

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

    _generic_mimetypes = {
        None,
        'application/octet-stream',
        }
    @cached_property
    def mimetype(self):
        mime, encoding = mimetypes.guess_type(self.path)
        mimetype = "%s%s%s" % (mime or "application/octet-stream", "; " if encoding else "", encoding or "")
        if mime in self._generic_mimetypes:
            try:
                output = subprocess.check_output(("file", "-ib", self.path)).decode('utf8').strip()
                if self.re_mime_validate.match(output):
                    # 'file' command can return status zero with invalid output
                    mimetype = output
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        return mimetype

    @cached_property
    def is_directory(self):
        return self.type.endswith("directory") or \
               self.type.endswith("symlink") and \
               os.path.isdir(self.path)

    @cached_property
    def parent(self):
        return File(os.path.dirname(self.path))

    @property
    def mtime(self):
        return self.stats.st_mtime

    @property
    def modified(self):
        return datetime.datetime.fromtimestamp(self.mtime).strftime('%Y.%m.%d %H:%M:%S')

    @property
    def size(self):
        size, unit = fmt_size(self.stats.st_size, self.app.config["use_binary_multiples"])
        if unit == binary_units[0]:
            return "%d %s" % (size, unit)
        return "%.2f %s" % (size, unit)

    @property
    def relpath(self):
        return relativize_path(self.path, self.app.config['directory_base'])

    @property
    def basename(self):
        return os.path.basename(self.path)

    @property
    def dirname(self):
        return os.path.dirname(self.path)

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

    @classmethod
    def listdir_order(cls, path):
        return not os.path.isdir(path), os.path.basename(path).lower()

    def listdir(self):
        pjoin = os.path.join # minimize list comprehension overhead
        content = [pjoin(self.path, i) for i in os.listdir(self.path)]
        content.sort(key=self.listdir_order)
        for i in content:
            yield self.__class__(i)


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

def root_path(path, os_sep=os.sep):
    '''
    Get root of given path.

    :param path: absolute path
    :param os_sep: path component separator, defaults to current OS separator
    :return: path
    :rtype: str or unicode
    '''
    if os_sep == '\\' and path.startswith('//'):
        return '//%s' % path[2:].split('/')[0]
    return path.split(os_sep)[0] or '/'

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
    prefix = os.path.commonprefix((path, base))
    if not prefix or prefix == root_path(base, os_sep):
        raise OutsideDirectoryBase("%r is not under %r" % (path, base))
    prefix_len = len(prefix)
    if not prefix.endswith(os_sep):
        prefix_len += len(os_sep)
    relpath = path[prefix_len:]
    return relpath

restricted_names = ('.', '..', '::', os.sep)
restricted_chars = '\/\0'
common_path_separators = '\\/'
nt_device_names = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1', 'LPT2', 'LPT3', 'PRN', 'NUL')
fs_encoding = 'unicode' if os.name == 'nt' else sys.getfilesystemencoding() or 'ascii'
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
    for sep in common_path_separators:
        if sep in path:
            _, path = path.rsplit(sep, 1)

    for character in restricted_chars:
        path = path.replace(character, '_')

    if destiny_os == 'nt':
        fpc = path.split('.', 1)[0].upper()
        if fpc in nt_device_names:
            return ''

    if path in restricted_names:
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
