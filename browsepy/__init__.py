#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import os
import os.path
import itertools

from flask import Flask, Response, request, render_template, redirect, \
                  url_for, send_from_directory, stream_with_context, \
                  make_response
from werkzeug.exceptions import NotFound

from .__meta__ import __app__, __version__, __license__, __author__
from .managers import MimetypeActionManager
from .file import File, TarFileStream, \
                  OutsideRemovableBase, OutsideDirectoryBase, \
                  relativize_path, secure_filename, fs_encoding
from .compat import PY_LEGACY, range

__basedir__ = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
    static_url_path = '/static',
    static_folder = os.path.join(__basedir__, "static"),
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
    plugin_modules = [],
    )

if "BROWSEPY_SETTINGS" in os.environ:
    app.config.from_envvar("BROWSEPY_SETTINGS")

mimetype_action_manager = MimetypeActionManager(app)

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

def empty_iterable(iterable):
    '''
    Get if iterable is empty, and return a new iterable.

    :param iterable: iterable
    :return: whether iterable is empty or not, and iterable
    :rtype: tuple of bool and iterable
    '''
    try:
        rest = iter(iterable)
        first = next(rest)
        return False, itertools.chain((first,), rest)
    except StopIteration:
        return True, iter(())

def stream_template(template_name, **context):
    '''
    Some templates can be huge, this function returns an streaming response,
    sending the content in chunks and preventing from timeout.

    :param template_name: template
    :param **context: parameters for templates.
    :yields: HTML strings
    '''
    app.update_template_context(context)
    template = app.jinja_env.get_template(template_name)
    stream = template.generate(context)
    return Response(stream_with_context(stream))

@app.before_first_request
def finish_initialization():
    mimetype_action_manager = app.extensions['mimetype_action_manager']
    for module in app.config['plugin_modules']:
        mimetype_action_manager.load_plugin(module)

@app.context_processor
def template_globals():
    return {
        'len': len,
        }

@app.route("/browse", defaults={"path":""})
@app.route('/browse/<path:path>')
def browse(path):
    try:
        realpath = urlpath_to_abspath(path, app.config["directory_base"])
        directory = File(realpath)
        if directory.is_directory:
            files = directory.listdir()
            empty_files, files = empty_iterable(files)
            path = abspath_to_urlpath(realpath, app.config["directory_base"])
            return stream_template("browse.html",
                dirbase = os.path.basename(app.config["directory_base"]) or '/',
                path = path,
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
        realpath = urlpath_to_abspath(path, app.config["directory_base"])
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
        realpath = urlpath_to_abspath(path, app.config["directory_base"])
        return File(realpath).download()
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/download/directory/<path:path>.tgz")
def download_directory(path):
    try:
        # Force download whatever is returned
        realpath = urlpath_to_abspath(path, app.config["directory_base"])
        return File(realpath).download()
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/remove/<path:path>", methods=("GET", "POST"))
def remove(path):
    try:
        realpath = urlpath_to_abspath(path, app.config["directory_base"])
    except OutsideDirectoryBase:
        return NotFound()
    if request.method == 'GET':
        if not File(realpath).can_remove:
            return NotFound()
        return render_template('remove.html',
                               backurl = url_for("browse", path=path).rsplit("/", 1)[0],
                               path = path)
    try:
        f = File(realpath)
        p = f.parent
        f.remove()
    except OutsideRemovableBase:
        return NotFound()
    path = abspath_to_urlpath(p.path, app.config["directory_base"])
    return redirect(url_for(".browse", path=path))

@app.route("/upload", defaults={'path': ''}, methods=("POST",))
@app.route("/upload/<path:path>", methods=("POST",))
def upload(path):
    try:
        realpath = urlpath_to_abspath(path, app.config["directory_base"])
    except OutsideDirectoryBase:
        return NotFound()

    directory = File(realpath)
    if not directory.is_directory or not directory.can_upload:
        return NotFound()

    for f in request.files.values():
        filename = secure_filename(f.filename)
        if filename:
            definitive_filename = directory.choose_filename(filename)
            f.save(os.path.join(directory.path, definitive_filename))
    path = abspath_to_urlpath(realpath, app.config["directory_base"])
    return redirect(url_for(".browse", path=path))

@app.route("/")
def index():
    path = app.config["directory_start"] or app.config["directory_base"]
    if PY_LEGACY and not isinstance(path, unicode):
        path = path.decode(fs_encoding)
    try:
        relpath = File(path).relpath
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
