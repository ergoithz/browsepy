# -*- coding: UTF-8 -*-

import os
import os.path
import functools

from flask import Blueprint, render_template, request, redirect, url_for, \
                  session, current_app
from werkzeug.exceptions import NotFound

from browsepy import get_cookie_browse_sorting, browse_sortkey_reverse
from browsepy.file import Node, abspath_to_urlpath, secure_filename, \
                          current_restricted_chars, common_path_separators
from browsepy.compat import re_escape, FileNotFoundError
from browsepy.exceptions import OutsideDirectoryBase
from browsepy.utils import stream_template, ppath

from .exceptions import FileActionsException, \
                        InvalidClipboardItemsError, \
                        InvalidClipboardModeError, \
                        InvalidDirnameError, \
                        DirectoryCreationError

from . import utils


actions = Blueprint(
    'file_actions',
    __name__,
    url_prefix='/file-actions',
    template_folder=ppath('templates', module=__name__),
    static_folder=ppath('static', module=__name__),
)

re_basename = '^[^ {0}]([^{0}]*[^ {0}])?$'.format(
    re_escape(current_restricted_chars + common_path_separators)
    )


@actions.route('/create/directory', methods=('GET', 'POST'),
               defaults={'path': ''})
@actions.route('/create/directory/<path:path>', methods=('GET', 'POST'))
def create_directory(path):
    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if not directory.is_directory or not directory.can_upload:
        return NotFound()

    if request.method == 'GET':
        return render_template(
            'create_directory.file_actions.html',
            file=directory,
            re_basename=re_basename,
            )

    basename = request.form['name']
    if secure_filename(basename) != basename or not basename:
        raise InvalidDirnameError(
            path=directory.path,
            name=basename,
            )

    try:
        os.mkdir(os.path.join(directory.path, basename))
    except BaseException as e:
        raise DirectoryCreationError.from_exception(
            e,
            path=directory.path,
            name=basename
            )

    return redirect(url_for('browse', path=directory.urlpath))


@actions.route('/selection', methods=('GET', 'POST'), defaults={'path': ''})
@actions.route('/selection/<path:path>', methods=('GET', 'POST'))
def selection(path):
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)

    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if directory.is_excluded or not directory.is_directory:
        return NotFound()

    if request.method == 'POST':
        action_fmt = 'action-{}'.format
        mode = None
        for action in ('cut', 'copy'):
            if request.form.get(action_fmt(action)):
                mode = action
                break

        clipboard = request.form.getlist('path')

        if mode in ('cut', 'copy'):
            session['clipboard:mode'] = mode
            session['clipboard:items'] = clipboard
            return redirect(url_for('browse', path=directory.urlpath))

        raise InvalidClipboardModeError(
            path=directory.path,
            mode=mode,
            clipboard=clipboard,
            )

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

    success, issues, nmode = utils.paste(directory, mode, clipboard)
    if clipboard and mode != nmode:
        session['mode'] = nmode
        mode = nmode

    if issues:
        raise InvalidClipboardItemsError(
            path=directory.path,
            mode=mode,
            clipboard=clipboard,
            issues=issues
            )

    if mode == 'cut':
        del session['clipboard:paths']

    return redirect(url_for('browse', path=directory.urlpath))


@actions.route('/clipboard/clear', defaults={'path': ''})
@actions.route('/clipboard/clear/<path:path>')
def clipboard_clear(path):
    if 'clipboard:paths' in session:
        del session['clipboard:paths']
    return redirect(url_for('browse', path=path))


@actions.errorhandler(FileActionsException)
def clipboard_error(e):
    file = Node(e.path) if hasattr(e, 'path') else None
    issues = getattr(e, 'issues', ())

    if session.get('clipboard:items'):
        clipboard = session['clipboard:mode']
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
    if last:
        # TODO: add warning message
        del data['clipboard:items']
        del data['clipboard:mode']
    return data


def detect_upload(directory):
    return directory.is_directory and directory.can_upload


def detect_clipboard(directory):
    return directory.is_directory and session.get('clipboard:mode')


def detect_selection(directory):
    return directory.is_directory and \
            current_app.config.get('DIRECTORY_UPLOAD')


def excluded_clipboard(manager, path):
    if session.get('clipboard:mode') == 'cut':
        base = manager.app.config['DIRECTORY_BASE']
        clipboard = session.get('clipboard:items', ())
        return abspath_to_urlpath(path, base) in clipboard
    return False


def register_plugin(manager):
    '''
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''
    manager.register_exclude_function(
        functools.partial(excluded_clipboard, manager)
        )
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
