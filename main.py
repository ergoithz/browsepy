#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import subprocess
import mimetypes
import datetime
import re
import functools
import itertools
import tarfile
import shutil
import threading
import time

import bottle

__app__ = "Browsepy"
__version__ = "0.1"
__author__ = "Felipe A. Hernandez <ergoithz@gmail.com>"
__basedir__ = os.path.dirname(__file__)

app = bottle.Bottle()
app.config.update({
    "autojson": False, # Turns off the "autojson" feature
    "browsepy.title": "BrowsePy",
    "browsepy.static": os.path.abspath(os.path.join(__basedir__, "static")),
    "browsepy.mount": "/browsepy",
    "browsepy.directory_base": __basedir__,
    "browsepy.directory_start": __basedir__,
    "browsepy.directory_remove": __basedir__,
    "browsepy.extra_links": {},
    "browsepy.directory_tar_buffsize": 262144,
    })

try:
    import config
    app.config.update(
        ("%s.%s" % (section, key), value)
        for section in dir(config) if section[0] != "_"
        for key, value in getattr(config, section).iteritems()
        )
    del config
except ImportError:
    pass


class OptimizedSimpleTemplate(bottle.SimpleTemplate):
    '''
    SimpleTemplate with removed identss
    '''
    extensions = ("tpl",)
    defaults = {
        "app": app,
        "app_name": __app__,
        "app_author": __author__,
        "app_version": __version__
        }
    _trimmer = re.compile("(\n\s+)(?!<html)")
    def render(self, *args, **kwargs):
        data = bottle.SimpleTemplate.render(self, *args, **kwargs)
        # last replace is a workaround for \\ slashes non working
        return self._trimmer.sub("\n", data).replace("\\\\\n","").strip()


template = functools.partial(bottle.template, template_adapter=OptimizedSimpleTemplate)
view = functools.partial(bottle.view, template_adapter=OptimizedSimpleTemplate)


class attribute(object):
    """ ``attribute`` decorator is intended to promote a
        function call to object attribute. This means the
        function is called once and replaced with
        returned value.

        >>> class A:
        ...     def __init__(self):
        ...         self.counter = 0
        ...     @attribute
        ...     def count(self):
        ...         self.counter += 1
        ...         return self.counter
        >>> a = A()
        >>> a.count
        1
        >>> a.count
        1
    """
    __slots__ = ('f')

    def __init__(self, f):
        self.f = f

    def __get__(self, obj, t=None):
        f = self.f
        val = f(obj)
        setattr(obj, f.__name__, val)
        return val


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
            return TarFileStream(
                self.path,
                app.config["browsepy.directory_tar_buffsize"]
                )
        directory, name = os.path.split(self.path)
        return bottle.static_file(name, root=directory, mimetype=self.mimetype,
                                  download=name)

    @attribute
    def can_download(self):
        return True #not self.is_directory

    @attribute
    def can_remove(self):
        dirbase = app.config["browsepy.directory_remove"]
        base = dirbase + os.sep
        return self.path.startswith(base)

    @attribute
    def stats(self):
        return os.stat(self.path)

    _generic_mimetypes = {
        None,
        'application/octet-stream',
        }
    @attribute
    def mimetype(self):
        mime, encoding = mimetypes.guess_type(self.path)
        if mime in self._generic_mimetypes:
            try:
                return subprocess.check_output(("file", "-ib", self.path))
            except:
                pass
        return "%s;%s" % (mime or "default", encoding or "default")

    @attribute
    def is_directory(self):
        return self.type.endswith("directory") or \
               self.type.endswith("symlink") and os.path.isdir(self.path)

    @property
    def mtime(self):
        return self.stats.st_mtime

    @property
    def modified(self):
        return datetime.datetime.fromtimestamp(self.mtime).strftime('%Y.%m.%d %H:%M:%S')

    @property
    def size(self):
        return "%.2f %s" % fmt_size(self.stats.st_size)

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
        dirbase = app.config["browsepy.directory_base"]
        content = sorted(
            (os.path.join(path, i) for i in os.listdir(path)),
            key=cls.listdir_order
            )
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


class OutsideDirectoryBase(Exception):
    pass


class OutsideRemovableBase(Exception):
    pass


fmt_sizes = ("B", "KiB", "MiB", "GiB")
def fmt_size(size):
    for fmt in fmt_sizes[:-1]:
        if size < 1000:
            return (size, fmt)
        size /= 1024.
    return size, fmt_sizes[-1]

def relativize_path(path, include_base=False):
    dirbase = app.config["browsepy.directory_base"]
    if include_base:
        dirbase = os.path.dirname(dirbase)
    return path[len(dirbase + os.sep):]

def urlpath_to_abspath(path):
    dirbase = app.config["browsepy.directory_base"]
    base = dirbase + os.sep
    realpath = os.path.abspath(base + path)
    if realpath.startswith(base):
        return realpath
    raise OutsideDirectoryBase("%r is not under %r" % (realpath, dirbase))

def render_browser(data):
    '''
    Browser pages can be huge due a lot of files. This function yields the
    page for streaming (preventing from timeout).

    Params:
        data: dict-like with parameters for templates.

    Yields:
        HTML strings
    '''
    files = data.get("files", None)
    try:
        first_file = files.next() if files else None
    except StopIteration:
        files = None
        first_file = None

    data["has_files"] = not first_file is None
    yield template("browse.head", data)

    if files:
        data["f"] = first_file
        yield template("browse.row", data)
        for f in files:
            data["f"] = f
            yield template("browse.row", data)
    yield template("browse.tail", data)

    #for k, v in data["old_request"].iteritems():
    #    if bottle.request[k] != v:
    #        print k, v, "!=", bottle.request[k]

@app.route('/browse/<path:path>', name="browse")
def browse(path):
    try:
        realpath = urlpath_to_abspath(path)
        if os.path.isdir(realpath):
            return render_browser({
                "path": relativize_path(realpath, True),
                "files": File.listdir(realpath),
                "old_request": dict(bottle.request),
                })
        elif os.path.isfile(realpath):
            return bottle.static_file(
                os.path.basename(realpath),
                os.path.dirname(realpath))
    except OutsideDirectoryBase:
        pass
    bottle.abort(404, "Not found")

@app.route("/browse", name="base")
def base():
    dirbase = app.config["browsepy.directory_base"]
    return render_browser({
        "topdir": True,
        "path": os.path.basename(dirbase),
        "files": File.listdir(dirbase),
        "old_request": dict(bottle.request),
        })

@app.route("/download/file/<path:path>", name="download_file")
def download_file(path):
    try:
        realpath = urlpath_to_abspath(path)
        return File(realpath).download()
    except OutsideDirectoryBase:
        bottle.abort(404, "Not found")

@app.route("/download/directory/<path:path>.tgz", name="download_directory")
def download_directory(path):
    try:
        # Force download whatever is returned
        bottle.response.set_header("Content-Type", "application/octet-stream")
        realpath = urlpath_to_abspath(path)
        return File(realpath).download()
    except OutsideDirectoryBase:
        bottle.abort(404, "Not found")

@app.get("/remove/<path:path>", name="remove_confirm")
@view("remove")
def remove_confirm(path):
    return {
        "backurl": app.get_url("browse", path=path).rsplit("/", 1)[0],
        "path": path
        }

@app.post("/remove/<path:path>", name="remove")
def remove(path):
    try:
        realpath = urlpath_to_abspath(path)
        File(realpath).remove()
    except (OutsideDirectoryBase, OutsideRemovableBase):
        bottle.abort(404, "Not found")
    else:
        bottle.redirect(bottle.request.forms.backurl)

@app.route("/", name="index")
@view("index")
def index():
    links = {"Browse files": app.get_url("base")}
    links.update(app.config["browsepy.extra_links"])
    return {"extra_links": sorted(links.iteritems())}

@app.route("/static/<path:path>", name="static")
def static(path):
    '''
    Static endpoint.
    Static files always should be served by server instead of from application,
    nothaways this is useful for debug and template links using `app.geturl`.
    '''
    return bottle.static_file(path, app.config["browsepy.static"])


if __name__ == "__main__":
    os.system("fuser -k -n tcp 8080")
    if app.config["browsepy.mount"]:
        p = bottle.Bottle()
        p.mount("/browsepy", app)
    else:
        p = app

    bottle.debug(True)
    bottle.run(p, host='localhost', port=8080, debug=True, reloader=True)
