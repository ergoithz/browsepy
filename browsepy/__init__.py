# -*- coding: UTF-8 -*-

__version__ = '0.5.6'

import logging
import os
import os.path

import cookieman

from flask import request, render_template, redirect, \
                  url_for, send_from_directory, \
                  make_response, session
from werkzeug.exceptions import NotFound

from .appconfig import Flask
from .manager import PluginManager
from .file import Node, secure_filename
from .utils import stream_template
from .exceptions import OutsideRemovableBase, OutsideDirectoryBase, \
                        InvalidFilenameError, InvalidPathError
from . import compat
from . import utils

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_url_path='/static',
    static_folder=utils.ppath('static'),
    template_folder=utils.ppath('templates'),
    )
app.config.update(
    SECRET_KEY=utils.random_string(4096),
    APPLICATION_NAME='browsepy',
    directory_base=compat.getcwd(),
    directory_start=None,
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
app.session_interface = cookieman.CookieMan()

if 'BROWSEPY_SETTINGS' in os.environ:
    app.config.from_envvar('BROWSEPY_SETTINGS')

plugin_manager = PluginManager(app)


@app.session_interface.register('browse:sort')
def shrink_browse_sort(data, last):
    if data['browse:sort'] and not last:
        data['browse:sort'].pop()
    else:
        del data['browse:sort']
    return data


def get_cookie_browse_sorting(path, default):
    '''
    Get sorting-cookie data for path of current request.

    :returns: sorting property
    :rtype: string
    '''
    if request:
        for cpath, cprop in session.get('browse:sort', ()):
            if path == cpath:
                return cprop
    return default


def browse_sortkey_reverse(prop):
    '''
    Get sorting function for directory listing based on given attribute
    name, with some caveats:
    * Directories will be first.
    * If *name* is given, link widget lowercase text will be used instead.
    * If *size* is given, bytesize will be used.

    :param prop: file attribute name
    :type prop: str
    :returns: tuple with sorting function and reverse bool
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


@app.context_processor
def template_globals():
    return {
        'manager': app.extensions['plugin_manager'],
        'len': len,
        }


@app.route('/sort/<string:property>', defaults={'path': ''})
@app.route('/sort/<string:property>/<path:path>')
def sort(property, path):
    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not directory.is_directory or directory.is_excluded:
        return NotFound()

    if request:
        session['browse:sort'] = \
            [(path, property)] + session.get('browse:sort', [])
    return redirect(url_for(".browse", path=directory.urlpath))


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

    file.remove()
    return redirect(url_for(".browse", path=file.parent.urlpath))


@app.route("/upload", defaults={'path': ''}, methods=("POST",))
@app.route("/upload/<path:path>", methods=("POST",))
def upload(path):
    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if (
      not directory.is_directory or
      not directory.can_upload or
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
            else:
                raise InvalidFilenameError(
                    path=directory.path,
                    filename=f.filename
                    )
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


@app.errorhandler(InvalidPathError)
def bad_request_error(e):
    file = None
    if hasattr(e, 'path'):
        if isinstance(e, InvalidFilenameError):
            file = Node(e.path)
        else:
            file = Node(e.path).parent
    return render_template('400.html', file=file, error=e), 400


@app.errorhandler(OutsideRemovableBase)
@app.errorhandler(404)
def page_not_found_error(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):  # pragma: no cover
    logger.exception(e)
    return getattr(e, 'message', 'Internal server error'), 500
