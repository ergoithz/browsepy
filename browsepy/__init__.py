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

from .__meta__ import __app__, __version__, __license__, __author__  # noqa
from .manager import PluginManager
from .file import Node, OutsideRemovableBase, OutsideDirectoryBase, \
                  secure_filename
from . import compat

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
        '',
        ),
    )

if "BROWSEPY_SETTINGS" in os.environ:
    app.config.from_envvar("BROWSEPY_SETTINGS")

plugin_manager = PluginManager(app)


def cookie_browse_sorting():
    '''
    Get sorting-cookie data of current request.

    :returns: sorting-cookie data as dict
    :rtype: dict
    '''
    try:
        data = request.cookies.get('browse-sorting', 'e30=').encode('ascii')
        return json.loads(base64.b64decode(data).decode('utf-8'))
    except (ValueError, TypeError, KeyError) as e:
        print(e)
        return {}


def browse_sortkey_reverse(prop):
    '''
    Get sorting function for browse

    :returns: tuple with sorting gunction and reverse bool
    :rtype: tuple of a dict and a bool
    '''
    if prop.startswith('-'):
        prop = prop[1:]
        reverse = True
    elif prop.startswith('+'):
        prop = prop[1:]
        reverse = False
    else:
        reverse = False

    if prop == 'text':
        return (
            lambda x: (
                x.is_directory == reverse,
                x.default_action[1].text.lower()
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

    if not directory.is_directory:
        return NotFound()

    data = cookie_browse_sorting()
    data[path] = property
    raw_data = json.dumps(data).encode('utf-8')

    response = redirect(url_for(".browse", path=directory.urlpath))
    response.set_cookie('browse-sorting', base64.b64encode(raw_data))
    return response


@app.route("/browse", defaults={"path": ""})
@app.route('/browse/<path:path>')
def browse(path):
    sort_property = cookie_browse_sorting().get(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)

    try:
        directory = Node.from_urlpath(path)
        if directory.is_directory:
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
        if file.is_file:
            return send_from_directory(file.parent.path, file.name)
    except OutsideDirectoryBase:
        pass
    return NotFound()


@app.route("/download/file/<path:path>")
def download_file(path):
    try:
        file = Node.from_urlpath(path)
        if file.is_file:
            return file.download()
    except OutsideDirectoryBase:
        pass
    return NotFound()


@app.route("/download/directory/<path:path>.tgz")
def download_directory(path):
    try:
        directory = Node.from_urlpath(path)
        if directory.is_directory:
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
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not directory.is_directory or not directory.can_upload:
        return NotFound()

    for f in request.files.values():
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
