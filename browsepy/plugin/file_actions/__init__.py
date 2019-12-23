"""Plugin module with filesystem functionality."""

from flask import Blueprint, render_template, request, redirect, url_for, \
                  session, current_app, g
from werkzeug.exceptions import NotFound

from browsepy import get_cookie_browse_sorting, browse_sortkey_reverse
from browsepy.file import Node, abspath_to_urlpath, current_restricted_chars, \
                          common_path_separators
from browsepy.compat import re_escape, FileNotFoundError
from browsepy.exceptions import OutsideDirectoryBase
from browsepy.stream import stream_template

from .exceptions import FileActionsException, \
                        InvalidClipboardItemsError, \
                        InvalidClipboardModeError, \
                        InvalidClipboardSizeError

from . import utils


actions = Blueprint(
    'file_actions',
    __name__,
    url_prefix='/file-actions',
    template_folder='templates',
    static_folder='static',
)

re_basename = '^[^ {0}]([^{0}]*[^ {0}])?$'.format(
    re_escape(current_restricted_chars + common_path_separators)
    )


@actions.route('/create/directory', methods=('GET', 'POST'),
               defaults={'path': ''})
@actions.route('/create/directory/<path:path>', methods=('GET', 'POST'))
def create_directory(path):
    """Handle request to create directory."""
    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not directory.is_directory or not directory.can_upload:
        return NotFound()

    if request.method == 'POST':
        path = utils.mkdir(directory.path, request.form['name'])
        base = current_app.config['DIRECTORY_BASE']
        return redirect(
            url_for('browsepy.browse', path=abspath_to_urlpath(path, base))
            )

    return render_template(
        'create_directory.file_actions.html',
        file=directory,
        re_basename=re_basename,
        )


@actions.route('/selection', methods=('GET', 'POST'), defaults={'path': ''})
@actions.route('/selection/<path:path>', methods=('GET', 'POST'))
def selection(path):
    """Handle file selection clipboard request."""
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)

    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if directory.is_excluded or not directory.is_directory:
        return NotFound()

    if request.method == 'POST':
        mode = (
            'cut' if request.form.get('action-cut') else
            'copy' if request.form.get('action-copy') else
            None
            )

        clipboard = request.form.getlist('path')

        if mode is None:
            raise InvalidClipboardModeError(
                path=directory.path,
                clipboard=clipboard,
                )

        session['clipboard:mode'] = mode
        session['clipboard:items'] = clipboard
        return redirect(url_for('browsepy.browse', path=directory.urlpath))

    return stream_template(
        'selection.file_actions.html',
        file=directory,
        mode=session.get('clipboard:mode'),
        clipboard=session.get('clipboard:items', ()),
        cut_support=any(node.can_remove for node in directory.listdir()),
        sort_property=sort_property,
        sort_fnc=sort_fnc,
        sort_reverse=sort_reverse,
        )


@actions.route('/clipboard/paste', defaults={'path': ''})
@actions.route('/clipboard/paste/<path:path>')
def clipboard_paste(path):
    """Handle clipboard paste-here request."""
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

    mode = session.get('clipboard:mode')
    clipboard = session.get('clipboard:items', ())

    g.file_actions_paste = True  # disable exclude function
    success, issues = utils.paste(directory, mode, clipboard)

    if issues:
        raise InvalidClipboardItemsError(
            path=directory.path,
            mode=mode,
            clipboard=clipboard,
            issues=issues
            )

    if mode == 'cut':
        session.pop('clipboard:mode', None)
        session.pop('clipboard:items', None)

    return redirect(url_for('browsepy.browse', path=directory.urlpath))


@actions.route('/clipboard/clear', defaults={'path': ''})
@actions.route('/clipboard/clear/<path:path>')
def clipboard_clear(path):
    """Handle clear clipboard request."""
    session.pop('clipboard:mode', None)
    session.pop('clipboard:items', None)
    return redirect(url_for('browsepy.browse', path=path))


@actions.errorhandler(FileActionsException)
def file_actions_error(e):
    """Serve informative error page on plugin errors."""
    file = Node(e.path) if hasattr(e, 'path') else None
    issues = getattr(e, 'issues', ())

    clipboard = session.get('clipboard:items')
    if clipboard and issues:
        for issue in issues:
            if isinstance(issue.error, FileNotFoundError):
                path = issue.item.urlpath
                if path in clipboard:
                    clipboard.remove(path)
                    session.modified = True

    return (
        render_template(
            '400.file_actions.html',
            error=e,
            file=file,
            mode=session.get('clipboard:mode'),
            clipboard=session.get('clipboard:items', ()),
            issues=issues,
            ),
        400
        )


def shrink_session(data, last):
    """Session shrinking logic (only obeys final attempt)."""
    if last:
        raise InvalidClipboardSizeError(
            mode=data.pop('clipboard:mode', None),
            clipboard=data.pop('clipboard:items', None),
            )
    return data


def detect_upload(directory):
    """Detect if directory node can be used as clipboard target."""
    return directory.is_directory and directory.can_upload


def detect_clipboard(directory):
    """Detect if clipboard is available on given directory node."""
    return directory.is_directory and session.get('clipboard:mode')


def detect_selection(directory):
    """Detect if file selection is available on given directory node."""
    return (
        directory.is_directory and
        current_app.config.get('DIRECTORY_UPLOAD')
        )


def excluded_clipboard(path):
    """
    Check if given path should be ignored when pasting clipboard.

    :param path: path to check
    :type path: str
    :return: wether path should be excluded or not
    :rtype: str
    """
    if (
      not getattr(g, 'file_actions_paste', False) and
      session.get('clipboard:mode') == 'cut'
      ):
        base = current_app.config['DIRECTORY_BASE']
        clipboard = session.get('clipboard:items', ())
        return abspath_to_urlpath(path, base) in clipboard
    return False


def register_plugin(manager):
    """
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    """
    manager.register_exclude_function(excluded_clipboard)
    manager.register_blueprint(actions)
    manager.register_widget(
        place='styles',
        type='stylesheet',
        endpoint='file_actions.static',
        filename='browse.css',
        filter=detect_clipboard,
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.create_directory',
        text='Create directory',
        filter=detect_upload,
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.selection',
        filter=detect_selection,
        text='Selection...',
        )
    manager.register_widget(
        place='header',
        type='html',
        html=lambda file: render_template(
            'widget.clipboard.file_actions.html',
            file=file,
            mode=session.get('clipboard:mode'),
            clipboard=session.get('clipboard:items', ()),
            ),
        filter=detect_clipboard,
        )
    manager.register_session(
        ('clipboard:items', 'clipboard:mode'),
        shrink_session,
        )
