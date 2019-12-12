"""Browsepy simple file server."""

__version__ = '0.6.0'

import logging
import os
import os.path
import time

import cookieman

from flask import request, render_template, jsonify, redirect, \
                  url_for, send_from_directory, \
                  session, abort

from .appconfig import Flask
from .manager import PluginManager
from .file import Node, secure_filename
from .stream import tarfile_extension, stream_template
from .http import etag
from .exceptions import OutsideRemovableBase, OutsideDirectoryBase, \
                        InvalidFilenameError, InvalidPathError

from . import compat

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static',
    )
app.config.update(
    SECRET_KEY=os.urandom(4096),
    APPLICATION_NAME='browsepy',
    APPLICATION_TIME=None,
    DIRECTORY_BASE=compat.getcwd(),
    DIRECTORY_START=None,
    DIRECTORY_REMOVE=None,
    DIRECTORY_UPLOAD=None,
    DIRECTORY_TAR_BUFFSIZE=262144,
    DIRECTORY_TAR_COMPRESSION='gzip',
    DIRECTORY_TAR_EXTENSION=None,
    DIRECTORY_TAR_COMPRESSLEVEL=1,
    DIRECTORY_DOWNLOADABLE=True,
    USE_BINARY_MULTIPLES=True,
    PLUGIN_MODULES=[],
    PLUGIN_NAMESPACES=(
        'browsepy.plugin',
        'browsepy_',
        '',
        ),
    EXCLUDE_FNC=None,
    )
app.jinja_env.add_extension('browsepy.transform.htmlcompress.HTMLCompress')
app.session_interface = cookieman.CookieMan()

if 'BROWSEPY_SETTINGS' in os.environ:
    app.config.from_envvar('BROWSEPY_SETTINGS')

plugin_manager = PluginManager(app)


@app.before_first_request
def prepare():
    config = app.config
    if config['APPLICATION_TIME'] is None:
        config['APPLICATION_TIME'] = time.time()


@app.url_defaults
def default_download_extension(endpoint, values):
    if endpoint == 'download_directory':
        values.setdefault(
            'extension',
            tarfile_extension(app.config['DIRECTORY_TAR_EXTENSION']),
            )


@app.session_interface.register('browse:sort')
def shrink_browse_sort(data, last):
    """Session `browse:short` size reduction logic."""
    if data['browse:sort'] and not last:
        data['browse:sort'].pop()
    else:
        del data['browse:sort']
    return data


def get_cookie_browse_sorting(path, default):
    """
    Get sorting-cookie data for path of current request.

    :returns: sorting property
    :rtype: string
    """
    if request:
        for cpath, cprop in session.get('browse:sort', ()):
            if path == cpath:
                return cprop
    return default


def browse_sortkey_reverse(prop):
    """
    Get sorting function for directory listing based on given attribute
    name, with some caveats:
    * Directories will be first.
    * If *name* is given, link widget lowercase text will be used instead.
    * If *size* is given, bytesize will be used.

    :param prop: file attribute name
    :type prop: str
    :returns: tuple with sorting function and reverse bool
    :rtype: tuple of a dict and a bool
    """
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
    directory = Node.from_urlpath(path)
    if directory.is_directory and not directory.is_excluded:
        session['browse:sort'] = \
            [(path, property)] + session.get('browse:sort', [])
        return redirect(url_for('.browse', path=directory.urlpath))
    abort(404)


@app.route('/browse', defaults={'path': ''})
@app.route('/browse/<path:path>')
def browse(path):
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)
    directory = Node.from_urlpath(path)
    if directory.is_directory and not directory.is_excluded:
        response = stream_template(
            'browse.html',
            file=directory,
            sort_property=sort_property,
            sort_fnc=sort_fnc,
            sort_reverse=sort_reverse,
            )
        response.last_modified = max(
            directory.content_mtime,
            app.config['APPLICATION_TIME'],
            )
        response.set_etag(
            etag(
                content_mtime=directory.content_mtime,
                sort_property=sort_property,
                ),
            )
        response.make_conditional(request)
        return response
    abort(404)


@app.route('/open/<path:path>', endpoint='open')
def open_file(path):
    file = Node.from_urlpath(path)
    if file.is_file and not file.is_excluded:
        return send_from_directory(file.parent.path, file.name)
    abort(404)


@app.route('/download/file/<path:path>')
def download_file(path):
    file = Node.from_urlpath(path)
    if file.is_file and not file.is_excluded:
        return file.download()
    abort(404)


@app.route('/download/directory.<string:extension>', defaults={'path': ''})
@app.route('/download/directory/?<path:path>.<string:extension>')
def download_directory(path, extension):
    if extension != tarfile_extension(app.config['DIRECTORY_TAR_COMPRESSION']):
        abort(404)
    directory = Node.from_urlpath(path)
    if directory.is_directory and not directory.is_excluded:
        return directory.download()
    abort(404)


@app.route('/remove/<path:path>', methods=('GET', 'POST'))
def remove(path):
    file = Node.from_urlpath(path)
    if file.can_remove and not file.is_excluded:
        if request.method == 'GET':
            return render_template('remove.html', file=file)
        file.remove()
        return redirect(url_for(".browse", path=file.parent.urlpath))
    abort(404)


@app.route('/upload', defaults={'path': ''}, methods=('POST',))
@app.route('/upload/<path:path>', methods=('POST',))
def upload(path):
    directory = Node.from_urlpath(path)
    if (
      directory.is_directory and
      directory.can_upload and
      not directory.is_excluded
      ):
        files = (
            (secure_filename(file.filename), file)
            for values in request.files.listvalues()
            for file in values
            )
        for filename, file in files:
            if not filename:
                raise InvalidFilenameError(
                    path=directory.path,
                    filename=file.filename,
                    )
            filename = directory.choose_filename(filename)
            filepath = os.path.join(directory.path, filename)
            file.save(filepath)
        return redirect(url_for('.browse', path=directory.urlpath))
    abort(404)


@app.route('/<any("manifest.json", "browserconfig.xml"):filename>')
def metadata(filename):
    response = app.response_class(render_template(filename))
    response.last_modified = app.config['APPLICATION_TIME']
    response.make_conditional(request)
    return response


@app.route('/')
def index():
    path = app.config['DIRECTORY_START'] or app.config['DIRECTORY_BASE']
    return browse(Node(path).urlpath)


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
@app.errorhandler(OutsideDirectoryBase)
@app.errorhandler(404)
def page_not_found_error(e):
    return render_template('404.html'), 404


@app.errorhandler(Exception)
@app.errorhandler(500)
def internal_server_error(e):  # pragma: no cover
    logger.exception(e)
    return getattr(e, 'message', 'Internal server error'), 500
