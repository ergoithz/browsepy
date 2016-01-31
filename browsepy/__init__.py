#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path

from flask import Flask, Response, request, render_template, redirect, \
                  url_for, send_from_directory, stream_with_context, \
                  make_response
from werkzeug.exceptions import NotFound

from .__meta__ import __app__, __version__, __license__, __author__
from .manager import PluginManager
from .file import File, OutsideRemovableBase, OutsideDirectoryBase, secure_filename, fs_encoding
from .compat import PY_LEGACY

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
    plugin_namespaces = (
        'browsepy.plugin',
        '',
        ),
    )

if "BROWSEPY_SETTINGS" in os.environ:
    app.config.from_envvar("BROWSEPY_SETTINGS")

plugin_manager = PluginManager(app)

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

@app.context_processor
def template_globals():
    return {
        'manager': app.extensions['plugin_manager'],
        'len': len,
        }

@app.route("/browse", defaults={"path":""})
@app.route('/browse/<path:path>')
def browse(path):
    try:
        directory = File.from_urlpath(path)
        if directory.is_directory:
            files = directory.listdir()
            return stream_template("browse.html", file=directory)
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route('/open/<path:path>', endpoint="open")
def open_file(path):
    try:
        file = File.from_urlpath(path)
        if file.is_file:
            return send_from_directory(file.parent.path, file.name)
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/download/file/<path:path>")
def download_file(path):
    try:
        file = File.from_urlpath(path)
        if file.is_file:
            return file.download()
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/download/directory/<path:path>.tgz")
def download_directory(path):
    try:
        directory = File.from_urlpath(path)
        if directory.is_directory:
            return directory.download()
    except OutsideDirectoryBase:
        pass
    return NotFound()

@app.route("/remove/<path:path>", methods=("GET", "POST"))
def remove(path):
    try:
        file = File.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()
    if request.method == 'GET':
        if not file.can_remove:
            return NotFound()
        return render_template('remove.html', file=file)
    parent = file.parent
    if parent is None:
        # base is not removable
        return NotFound()

    try:
        file.remove()
    except OutsideRemovableBase:
        return NotFound()

    return redirect(url_for(".browse", path=parent.urlpath))

@app.route("/upload", defaults={'path': ''}, methods=("POST",))
@app.route("/upload/<path:path>", methods=("POST",))
def upload(path):
    try:
        directory = File.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not directory.is_directory or not directory.can_upload:
        return NotFound()

    for f in request.files.values():
        filename = secure_filename(f.filename)
        if filename:
            definitive_filename = directory.choose_filename(filename)
            f.save(os.path.join(directory.path, definitive_filename))
    return redirect(url_for(".browse", path=directory.urlpath))

@app.route("/")
def index():
    path = app.config["directory_start"] or app.config["directory_base"]
    if PY_LEGACY and not isinstance(path, unicode):
        path = path.decode(fs_encoding)
    try:
        urlpath = File(path).urlpath
    except OutsideDirectoryBase:
        return NotFound()
    return browse(urlpath)

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
