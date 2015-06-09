#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import os
import sys
import os.path
import subprocess
import mimetypes
import datetime
import itertools
import tarfile
import shutil
import threading
import codecs

from flask import Flask, Response, request, render_template, redirect, \
                   url_for, send_from_directory, stream_with_context, make_response
from werkzeug.exceptions import NotFound
from werkzeug.utils import cached_property

from .__meta__ import __app__, __version__, __license__, __author__

__basedir__ = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
    static_url_path = os.path.join(__basedir__, "static"),
    template_folder = os.path.join(__basedir__, "templates")
    )
app.config.update(
    directory_base = os.path.abspath(os.getcwd()),
    directory_start = os.path.abspath(os.getcwd()),
    directory_remove = None,
    directory_upload = None,
    directory_tar_buffsize = 262144,
    directory_downloadable = True,
    use_binary_multiples = True,
    )

if "BROWSEPY_SETTINGS" in os.environ:
    app.config.from_envvar("BROWSEPY_SETTINGS")

PY_LEGACY = sys.version_info[0] < 3
if PY_LEGACY:
    FileNotFoundError = type('FileNotFoundError', (OSError,), {})

undescore_replace = '%s:underscore' % __name__
codecs.register_error(undescore_replace,
                      (lambda error: (u'_', error.start + 1))
                      if PY_LEGACY else
                      (lambda error: ('_', error.start + 1))
                      )


class File(object):
    re_mime_validate = re.compile('\w+/\w+(; \w+=[^;]+)*')
    re_charset = re.compile('; charset=(?P<charset>[^;]+)')
    def __init__(self, path):
        self.path = path

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
                app.config["directory_tar_buffsize"]
                )
            return Response(stream, mimetype="application/octet-stream")
        directory, name = os.path.split(self.path)
        return send_from_directory(directory, name, as_attachment=True)

    @cached_property
    def can_download(self):
        return app.config['directory_downloadable'] or not self.is_directory

    @cached_property
    def can_remove(self):
        dirbase = app.config["directory_remove"]
        if dirbase:
            return self.path.startswith(dirbase + os.sep)
        return False

    @cached_property
    def can_upload(self):
        dirbase = app.config["directory_upload"]
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
        size, unit = fmt_size(self.stats.st_size, app.config["use_binary_multiples"])
        if unit == binary_units[0]:
            return "%d %s" % (size, unit)
        return "%.2f %s" % (size, unit)

    @property
    def relpath(self):
        return relativize_path(self.path)

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
    def __init__(self, path, buffsize=10240):
        self.path = path
        self.name = os.path.basename(path) + ".tgz"

        self._finished = 0
        self._want = 0
        self._data = bytes()
        self._add = threading.Event()
        self._result = threading.Event()
        self._tarfile = tarfile.open(fileobj=self, mode="w|gz", bufsize=buffsize) # stream write
        self._th = threading.Thread(target=self.fill)
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

def empty_iterable(iterable):
    try:
        rest = iter(iterable)
        first = next(rest)
        return False, itertools.chain((first,), rest)
    except StopIteration:
        return True, iter(())

def relativize_path(path):
    prefix = os.path.commonprefix((path, app.config["directory_base"]))
    prefix_len = len(prefix)
    if not prefix.endswith(os.sep):
        prefix_len += len(os.sep)
    return path[prefix_len:]

def urlpath_to_abspath(path):
    dirbase = app.config["directory_base"]
    prefix = dirbase
    if not prefix.endswith(os.sep):
        prefix += os.sep
    realpath = os.path.abspath(prefix + path)
    if dirbase == realpath or realpath.startswith(prefix):
        return realpath
    raise OutsideDirectoryBase("%r is not under %r" % (realpath, dirbase))

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
    :return: filename or empty string
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


def stream_template(template_name, **context):
    '''
    Some templates can be huge, this function returns an streaming response,
    sending the content in chunks and preventing from timeout.

    Params:
        template_name: template
        **context: parameters for templates.

    Yields:
        HTML strings
    '''
    app.update_template_context(context)
    template = app.jinja_env.get_template(template_name)
    stream = template.generate(context)
    return Response(stream_with_context(stream))


@app.context_processor
def template_globals():
    return {
        'len': len,
        }

@app.route("/browse", defaults={"path":""})
@app.route('/browse/<path:path>')
def browse(path):
    try:
        realpath = urlpath_to_abspath(path)
        directory = File(realpath)
        if directory.is_directory:
            files = directory.listdir()
            empty_files, files = empty_iterable(files)
            return stream_template("browsepy.browse.html",
                dirbase = os.path.basename(app.config["directory_base"]) or '/',
                path = relativize_path(realpath),
                upload = directory.can_upload,
                files = files,
                has_files = not empty_files
                )
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route('/open/<path:path>', endpoint="open")
def open_file(path):
    try:
        realpath = urlpath_to_abspath(path)
        if os.path.isfile(realpath):
            return send_from_directory(
                os.path.dirname(realpath),
                os.path.basename(realpath)
                )
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/download/file/<path:path>")
def download_file(path):
    try:
        realpath = urlpath_to_abspath(path)
        return File(realpath).download()
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/download/directory/<path:path>.tgz")
def download_directory(path):
    try:
        # Force download whatever is returned
        realpath = urlpath_to_abspath(path)
        return File(realpath).download()
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/remove/<path:path>", methods=("GET", "POST"))
def remove(path):
    try:
        realpath = urlpath_to_abspath(path)
    except OutsideDirectoryBase:
        return NotFound()
    if request.method == 'GET':
        if not File(realpath).can_remove:
            return NotFound()
        return render_template('browsepy.remove.html',
                               backurl = url_for("browse", path=path).rsplit("/", 1)[0],
                               path = path)
    try:
        f = File(realpath)
        p = f.parent
        f.remove()
    except OutsideRemovableBase:
        return NotFound()
    return redirect(url_for(".browse", path=relativize_path(p.path)))

@app.route("/upload/<path:path>", methods=("POST",))
def upload(path):
    try:
        realpath = urlpath_to_abspath(path)
    except OutsideDirectoryBase:
        return NotFound()

    directory = File(realpath)
    if not directory.is_directory or not directory.can_upload:
        return NotFound()

    for f in request.files.values():
        filename = secure_filename(f.filename)
        if filename:
            f.save(os.path.join(directory.path, filename))
    return redirect(url_for(".browse", path=relativize_path(realpath)))


@app.route("/")
def index():
    try:
        relpath = File(app.config["directory_start"] or
                       app.config["directory_base"]
                       ).relpath
    except OutsideDirectoryBase:
        return NotFound()
    return browse(relpath)

@app.after_request
def page_not_found(response):
    if response.status_code == 404:
        return make_response((render_template('404.html'), 404))
    return response

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e): # pragma: no cover
    import traceback
    traceback.print_exc()
    return getattr(e, 'message', 'Internal server error'), 500
