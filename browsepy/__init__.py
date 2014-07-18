#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import subprocess
import mimetypes
import datetime
import itertools
import tarfile
import shutil
import threading

from flask import Flask, Response, request, render_template, redirect, \
                   url_for, send_from_directory, stream_with_context
from werkzeug.exceptions import NotFound

__app__ = "Browsepy"
__version__ = "0.3"
__author__ = "Felipe A. Hernandez <ergoithz@gmail.com>"
__basedir__ = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
    static_url_path = os.path.join(__basedir__, "static"),
    template_folder = os.path.join(__basedir__, "templates")
    )
app.config.update(
    directory_base = os.path.abspath(os.getcwd()),
    directory_start = os.path.abspath(os.getcwd()),
    directory_remove = None,
    directory_tar_buffsize = 262144,
    directory_downloadable = True,
    use_binary_multiples = True,
    )

if "BROWSEPY_SETTINGS" in os.environ:
    app.config.from_envvar("BROWSEPY_SETTINGS")


class File(object):
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

    _can_download = None
    @property
    def can_download(self):
        if self._can_download is None:
            self._can_download = app.config['directory_downloadable'] \
                                 or not self.is_directory
        return self._can_download

    _can_remove = None
    @property
    def can_remove(self):
        if self._can_remove is None:
            dirbase = app.config["directory_remove"]
            if dirbase:
                base = dirbase + os.sep
                self._can_remove = self.path.startswith(base)
            else:
                self._can_remove = False
        return self._can_remove

    _stats = None
    @property
    def stats(self):
        if self._stats is None:
            self._stats = os.stat(self.path)
        return self._stats

    _generic_mimetypes = {
        None,
        'application/octet-stream',
        }
    _mimetype = None
    @property
    def mimetype(self):
        if self._mimetype is None:
            mime, encoding = mimetypes.guess_type(self.path)
            if mime in self._generic_mimetypes:
                try:
                    self._mimetype = subprocess.check_output(("file", "-ib", self.path)).decode('utf8')
                except:
                    self._mimetype = "%s;%s" % (mime or "default", encoding or "default")
            else:
                self._mimetype = "%s;%s" % (mime or "default", encoding or "default")
        return self._mimetype

    _is_directory = None
    @property
    def is_directory(self):
        if self._is_directory is None:
            self._is_directory = self.type.endswith("directory") or \
                                 self.type.endswith("symlink") and \
                                 os.path.isdir(self.path)
        return self._is_directory

    @property
    def mtime(self):
        return self.stats.st_mtime

    @property
    def modified(self):
        return datetime.datetime.fromtimestamp(self.mtime).strftime('%Y.%m.%d %H:%M:%S')

    @property
    def size(self):
        return "%.2f %s" % fmt_size(self.stats.st_size, app.config["use_binary_multiples"])

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
            return self.mimetype.split(";", 1)[-1]
        return "default"

    @classmethod
    def listdir_order(cls, path):
        return not os.path.isdir(path), os.path.basename(path).lower()

    @classmethod
    def listdir(cls, path):
        pjoin = os.path.join # minimize list comprehension overhead
        content = [pjoin(path, i) for i in os.listdir(path)]
        content.sort(key=cls.listdir_order)
        for i in content:
            yield cls(i)


class TarFileStream(object):
    '''
    Tarfile which compresses while reading for streaming.

    Buffsize can be provided, it must be 512 multiple (the tar block size) for
    compression.
    '''
    def __init__(self, path, buffsize=10240):
        self.path = path
        self.name = os.path.basename(path) + ".tgz"
        self._tarfile = tarfile.open(fileobj=self, mode="w|gz", bufsize=buffsize) # stream write
        self._finished = 0
        self._want = 0
        self._data = ""
        self._add = threading.Event()
        self._result = threading.Event()
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
            self._data = ""
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
        return True, ()

def relativize_path(path, include_base=False):
    dirbase = app.config["directory_base"]
    if include_base:
        dirbase = os.path.dirname(dirbase)
    return path[len(dirbase + os.sep):]

def urlpath_to_abspath(path):
    dirbase = app.config["directory_base"]
    base = dirbase + os.sep
    realpath = os.path.abspath(base + path)
    if realpath.startswith(base):
        return realpath
    raise OutsideDirectoryBase("%r is not under %r" % (realpath, dirbase))

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
        if os.path.isdir(realpath):
            files = File.listdir(realpath)
            empty_files, files = empty_iterable(files)
            return stream_template("browsepy.browse.html",
                dirbase = os.path.basename(app.config["directory_base"]) or '/',
                path = relativize_path(realpath, True),
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
        return NotFound()

@app.route("/remove/<path:path>")
def remove_confirm(path):
    return {
        "backurl": app.get_url("browse", path=path).rsplit("/", 1)[0],
        "path": path
        }

@app.route("/remove/<path:path>", methods=("POST",))
def remove(path):
    try:
        realpath = urlpath_to_abspath(path)
        File(realpath).remove()
    except (OutsideDirectoryBase, OutsideRemovableBase):
        return NotFound()
    else:
        return redirect(request.args.get("backurl") or url_for(".index"))

@app.route("/")
def index():
    try:
        relpath = File(app.config["directory_start"] or
                       app.config["directory_base"]
                       ).relpath
    except OutsideDirectoryBase as e:
        return NotFound()
    else:
        return browse(relpath)
