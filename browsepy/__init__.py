"""Browsepy simple file server."""

__version__ = '0.6.0'

import typing
import os
import os.path
import time

import cookieman

from flask import (
    request, render_template, redirect,
    url_for, send_from_directory,
    current_app, session, abort,
    )

import browsepy.mimetype as mimetype
import browsepy.compat as compat

from browsepy.appconfig import CreateApp
from browsepy.manager import PluginManager
from browsepy.file import Node, secure_filename
from browsepy.stream import tarfile_extension, stream_template
from browsepy.http import etag
from browsepy.exceptions import (
    OutsideRemovableBase, OutsideDirectoryBase,
    InvalidFilenameError, InvalidPathError
    )


create_app = CreateApp(
    __name__,
    static_folder='static',
    template_folder='templates',
    )


@create_app.register
def init_config():
    """Configure application."""
    current_app.config.update(
        SECRET_KEY=os.urandom(4096),
        APPLICATION_NAME='browsepy',
        APPLICATION_TIME=0,
        DIRECTORY_BASE=compat.getcwd(),
        DIRECTORY_START=None,
        DIRECTORY_REMOVE=None,
        DIRECTORY_UPLOAD=None,
        DIRECTORY_TAR_BUFFSIZE=262144,
        DIRECTORY_TAR_COMPRESSION='gzip',
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
    current_app.jinja_env.add_extension(
        'browsepy.transform.compress.TemplateCompress')

    if 'BROWSEPY_SETTINGS' in os.environ:
        current_app.config.from_envvar('BROWSEPY_SETTINGS')


@create_app.register
def init_plugins():
    """Configure plugin manager."""
    current_app.session_interface = cookieman.CookieMan()
    plugin_manager = PluginManager()
    plugin_manager.init_app(current_app)

    @current_app.session_interface.register('browse:sort')
    def shrink_browse_sort(data, last):
        """Session `browse:short` size reduction logic."""
        if data['browse:sort'] and not last:
            data['browse:sort'].pop()
        else:
            del data['browse:sort']
        return data


@create_app.before_first_request
def prepare_config():
    """Prepare runtime app config."""
    config = current_app.config
    if not config['APPLICATION_TIME']:
        config['APPLICATION_TIME'] = time.time()


@create_app.context_processor
def template_globals():
    """Get template globals."""
    return {
        'manager': current_app.extensions['plugin_manager'],
        'len': len,
        }


@create_app.url_defaults
def default_directory_download_extension(endpoint, values):
    """Set default extension for download_directory endpoint."""
    if endpoint == 'download_directory':
        compression = current_app.config['DIRECTORY_TAR_COMPRESSION']
        values.setdefault('ext', tarfile_extension(compression))


@create_app.errorhandler(InvalidPathError)
def bad_request_error(e):
    """Handle invalid requests errors, rendering HTTP 400 page."""
    file = None
    if hasattr(e, 'path'):
        file = Node(e.path)
        if not isinstance(e, InvalidFilenameError):
            file = file.parent
    return render_template('400.html', file=file, error=e), 400


@create_app.errorhandler(OutsideRemovableBase)
@create_app.errorhandler(OutsideDirectoryBase)
@create_app.errorhandler(404)
def page_not_found_error(e):
    """Handle resource not found errors, rendering 404 error page."""
    return render_template('404.html'), 404


@create_app.errorhandler(Exception)
@create_app.errorhandler(500)
def internal_server_error(e):  # pragma: no cover
    """Handle server errors, rendering 404 error page."""
    current_app.logger.exception(e)
    return getattr(e, 'message', 'Internal server error'), 500


def get_cookie_browse_sorting(path, default):
    # type: (str, str) -> str
    """
    Get sorting-cookie data for path of current request.

    :param path: path for sorting attribute
    :param default: default sorting attribute
    :return: sorting property
    """
    if request:
        for cpath, cprop in session.get('browse:sort', ()):
            if path == cpath:
                return cprop
    return default


def browse_sortkey_reverse(prop):
    # type: (str) -> typing.Tuple[typing.Callable[[Node], typing.Any], bool]
    """
    Get directory content sort function based on given attribute name.

    :param prop: file attribute name
    :return: tuple with sorting function and reverse bool

    The sort function takes some extra considerations:

    1. Directories will be always first.
    2. If *name* is given, link widget lowercase text will be used instead.
    3. If *size* is given, bytesize will be used.

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


@create_app.route('/sort/<string:property>', defaults={'path': ''})
@create_app.route('/sort/<string:property>/<path:path>')
def sort(property, path):
    """Handle sort request, add sorting rule to session."""
    directory = Node.from_urlpath(path)
    if directory.is_directory and not directory.is_excluded:
        session['browse:sort'] = \
            [(path, property)] + session.get('browse:sort', [])
        return redirect(url_for('.browse', path=directory.urlpath))
    abort(404)


@create_app.route('/browse', defaults={'path': ''})
@create_app.route('/browse/<path:path>')
def browse(path):
    """Handle browse request, serve directory listing."""
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)
    directory = Node.from_urlpath(path)
    if directory.is_directory and not directory.is_excluded:
        last_modified = max(
            directory.content_mtime,
            current_app.config['APPLICATION_TIME'],
            )
        response = stream_template(
            'browse.html',
            file=directory,
            sort_property=sort_property,
            sort_fnc=sort_fnc,
            sort_reverse=sort_reverse,
            )
        response.last_modified = last_modified
        response.set_etag(
            etag(
                last_modified=last_modified,
                sort_property=sort_property,
                ),
            )
        response.make_conditional(request)
        return response
    abort(404)


@create_app.route('/open/<path:path>', endpoint='open')
def open_file(path):
    """Handle open request, serve file."""
    file = Node.from_urlpath(path)
    if file.is_file and not file.is_excluded:
        return send_from_directory(file.parent.path, file.name)
    abort(404)


@create_app.route('/download/file/<path:path>')
def download_file(path):
    """Handle download request, serve file as attachment."""
    file = Node.from_urlpath(path)
    if file.is_file and not file.is_excluded:
        return file.download()
    abort(404)


@create_app.route('/download/directory.<string:ext>', defaults={'path': ''})
@create_app.route('/download/directory/?<path:path>.<string:ext>')
def download_directory(path, ext):
    """Handle download directory request, serve tarfile as attachment."""
    compression = current_app.config['DIRECTORY_TAR_COMPRESSION']
    if ext != tarfile_extension(compression):
        abort(404)
    directory = Node.from_urlpath(path)
    if directory.is_directory and not directory.is_excluded:
        return directory.download()
    abort(404)


@create_app.route('/remove/<path:path>', methods=('GET', 'POST'))
def remove(path):
    """Handle remove request, serve confirmation dialog."""
    file = Node.from_urlpath(path)
    if file.can_remove and not file.is_excluded:
        if request.method == 'GET':
            return render_template('remove.html', file=file)
        file.remove()
        return redirect(url_for(".browse", path=file.parent.urlpath))
    abort(404)


@create_app.route('/upload', defaults={'path': ''}, methods=('POST',))
@create_app.route('/upload/<path:path>', methods=('POST',))
def upload(path):
    """Handle upload request."""
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


@create_app.route('/<any("manifest.json", "browserconfig.xml"):filename>')
def metadata(filename):
    """Handle metadata request, serve browse metadata file."""
    last_modified = current_app.config['APPLICATION_TIME']
    response = stream_template(filename)
    response.content_type = mimetype.by_python(filename)
    response.last_modified = current_app.config['APPLICATION_TIME']
    response.set_etag(etag(last_modified=last_modified))
    response.make_conditional(request)
    return response


@create_app.route('/')
def index():
    """Handle index request, serve either start or base directory listing."""
    path = (
        current_app.config['DIRECTORY_START'] or
        current_app.config['DIRECTORY_BASE']
        )
    return browse(Node(path).urlpath)


app = create_app()
plugin_manager = app.extensions['plugin_manager']
