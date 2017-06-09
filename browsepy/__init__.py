#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import logging
import os
import os.path
import json
import base64

from flask import Flask, Response, request, render_template, redirect, \
                  url_for, send_from_directory, stream_with_context, \
                  make_response
from werkzeug.exceptions import NotFound

from .manager import PluginManager
from .file import Node, OutsideRemovableBase, OutsideDirectoryBase, \
                  secure_filename
from . import compat
from . import __meta__ as meta

__app__ = meta.app  # noqa
__version__ = meta.version  # noqa
__license__ = meta.license  # noqa
__author__ = meta.author  # noqa
__basedir__ = os.path.abspath(os.path.dirname(compat.fsdecode(__file__)))

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_url_path='/static',
    static_folder=os.path.join(__basedir__, "static"),
    template_folder=os.path.join(__basedir__, "templates")
    )
app.config.update(
    directory_base=compat.getcwd(),
    directory_start=compat.getcwd(),
    directory_remove=None,
    directory_upload=None,
    directory_tar_buffsize=262144,
    directory_downloadable=True,
    use_binary_multiples=True,
    plugin_modules=[],
    plugin_namespaces=(
        'browsepy.plugin',
        'browsepy_',
        '',
        ),
    exclude_fnc=None,
    )
app.jinja_env.add_extension('browsepy.transform.htmlcompress.HTMLCompress')

if "BROWSEPY_SETTINGS" in os.environ:
    app.config.from_envvar("BROWSEPY_SETTINGS")

plugin_manager = PluginManager(app)


def iter_cookie_browse_sorting(cookies):
    '''
    Get sorting-cookie from cookies dictionary.

    :yields: tuple of path and sorting property
    :ytype: 2-tuple of strings
    '''
    try:
        data = cookies.get('browse-sorting', 'e30=').encode('ascii')
        for path, prop in json.loads(base64.b64decode(data).decode('utf-8')):
            yield path, prop
    except (ValueError, TypeError, KeyError) as e:
        logger.exception(e)


def get_cookie_browse_sorting(path, default):
    '''
    Get sorting-cookie data for path of current request.

    :returns: sorting property
    :rtype: string
    '''
    if request:
        for cpath, cprop in iter_cookie_browse_sorting(request.cookies):
            if path == cpath:
                return cprop
    return default


def browse_sortkey_reverse(prop):
    '''
    Get sorting function for directory listing based on given attribute
    name, with some caveats:
    * Directories will be first.
    * If *name* is given, link widget lowercase text will be used istead.
    * If *size* is given, bytesize will be used.

    :param prop: file attribute name
    :returns: tuple with sorting gunction and reverse bool
    :rtype: tuple of a dict and a bool
    '''
    if prop.startswith('-'):
        prop = prop[1:]
        reverse = True
    else:
        reverse = False

    if prop == 'text':
        return (
            lambda x: (
                x.is_directory == reverse,
                x.link.text.lower() if x.link and x.link.text else x.name
                ),
            reverse
            )
    if prop == 'size':
        return (
            lambda x: (
                x.is_directory == reverse,
                x.stats.st_size
                ),
            reverse
            )
    return (
        lambda x: (
            x.is_directory == reverse,
            getattr(x, prop, None)
            ),
        reverse
        )


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


@app.route('/sort/<string:property>', defaults={"path": ""})
@app.route('/sort/<string:property>/<path:path>')
def sort(property, path):
    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not directory.is_directory or directory.is_excluded:
        return NotFound()

    data = [
        (cpath, cprop)
        for cpath, cprop in iter_cookie_browse_sorting(request.cookies)
        if cpath != path
        ]
    data.append((path, property))
    raw_data = base64.b64encode(json.dumps(data).encode('utf-8'))

    # prevent cookie becoming too large
    while len(raw_data) > 3975:  # 4000 - len('browse-sorting=""; Path=/')
        data.pop(0)
        raw_data = base64.b64encode(json.dumps(data).encode('utf-8'))

    response = redirect(url_for(".browse", path=directory.urlpath))
    response.set_cookie('browse-sorting', raw_data)
    return response


@app.route("/browse", defaults={"path": ""})
@app.route('/browse/<path:path>')
def browse(path):
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)

    try:
        directory = Node.from_urlpath(path)
        if directory.is_directory and not directory.is_excluded:
            return stream_template(
                'browse.html',
                file=directory,
                sort_property=sort_property,
                sort_fnc=sort_fnc,
                sort_reverse=sort_reverse
                )
    except OutsideDirectoryBase:
        pass
    return NotFound()


@app.route('/open/<path:path>', endpoint="open")
def open_file(path):
    try:
        file = Node.from_urlpath(path)
        if file.is_file and not file.is_excluded:
            return send_from_directory(file.parent.path, file.name)
    except OutsideDirectoryBase:
        pass
    return NotFound()


@app.route("/download/file/<path:path>")
def download_file(path):
    try:
        file = Node.from_urlpath(path)
        if file.is_file and not file.is_excluded:
            return file.download()
    except OutsideDirectoryBase:
        pass
    return NotFound()


@app.route("/download/directory/<path:path>.tgz")
def download_directory(path):
    try:
        directory = Node.from_urlpath(path)
        if directory.is_directory and not directory.is_excluded:
            return directory.download()
    except OutsideDirectoryBase:
        pass
    return NotFound()


@app.route("/remove/<path:path>", methods=("GET", "POST"))
def remove(path):
    try:
        file = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not file.can_remove or file.is_excluded:
        return NotFound()

    if request.method == 'GET':
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
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if (
      not directory.is_directory or not directory.can_upload or
      directory.is_excluded
      ):
        return NotFound()

    for v in request.files.listvalues():
        for f in v:
            filename = secure_filename(f.filename)
            if filename:
                filename = directory.choose_filename(filename)
                filepath = os.path.join(directory.path, filename)
                f.save(filepath)
    return redirect(url_for(".browse", path=directory.urlpath))


@app.route("/")
def index():
    path = app.config["directory_start"] or app.config["directory_base"]
    try:
        urlpath = Node(path).urlpath
    except OutsideDirectoryBase:
        return NotFound()
    return browse(urlpath)


@app.after_request
def page_not_found(response):
    if response.status_code == 404:
        return make_response((render_template('404.html'), 404))
    return response


@app.errorhandler(404)
def page_not_found_error(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):  # pragma: no cover
    logger.exception(e)
    return getattr(e, 'message', 'Internal server error'), 500
