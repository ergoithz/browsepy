#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import shutil

from flask import Blueprint, render_template, request, redirect, url_for, \
                  make_response
from werkzeug.exceptions import NotFound

from browsepy import get_cookie_browse_sorting, browse_sortkey_reverse
from browsepy.file import Node, abspath_to_urlpath, secure_filename, \
                          current_restricted_chars, common_path_separators
from browsepy.compat import map, re_escape, FileNotFoundError
from browsepy.exceptions import OutsideDirectoryBase

from .clipboard import Clipboard
from .exceptions import FileActionsException, ClipboardException, \
                        InvalidClipboardModeError, InvalidClipboardItemError, \
                        MissingClipboardItemError, InvalidDirnameError


__basedir__ = os.path.dirname(os.path.abspath(__file__))

actions = Blueprint(
    'file_actions',
    __name__,
    url_prefix='/file-actions',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
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

    os.mkdir(os.path.join(directory.path, basename))

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

        if mode in ('cut', 'copy'):
            response = redirect(url_for('browse', path=directory.urlpath))
            clipboard = Clipboard(request.form.getlist('path'), mode)
            clipboard.to_response(response)
            return response

        return redirect(request.path)

    clipboard = Clipboard.from_request()
    clipboard.mode = 'select'  # disables exclusion
    return render_template(
        'selection.file_actions.html',
        file=directory,
        clipboard=clipboard,
        cut_support=any(node.can_remove for node in directory.listdir()),
        sort_property=sort_property,
        sort_fnc=sort_fnc,
        sort_reverse=sort_reverse,
        )


@actions.route('/clipboard/paste', defaults={'path': ''})
@actions.route('/clipboard/paste/<path:path>')
def clipboard_paste(path):

    def copy(target, node, join_fnc=os.path.join):
        dest = join_fnc(
            target.path,
            target.choose_filename(node.name)
            )
        if node.is_directory:
            shutil.copytree(node.path, dest)
        else:
            shutil.copy2(node.path, dest)

    def cut(target, node, join_fnc=os.path.join):
        if node.parent.path != target.path:
            dest = join_fnc(
                target.path,
                target.choose_filename(node.name)
                )
            shutil.move(node.path, dest)

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

    response = redirect(url_for('browse', path=directory.urlpath))
    clipboard = Clipboard.from_request()
    mode = clipboard.mode
    clipboard.mode = 'paste'  # disables exclusion

    nodes = [node for node in map(Node.from_urlpath, clipboard)]

    if mode == 'cut':
        paste_fnc = cut
        for node in nodes:
            if node.is_excluded or not node.can_remove:
                raise InvalidClipboardItemError(
                    path=directory.path,
                    item=node.urlpath
                    )
    elif mode == 'copy':
        paste_fnc = copy
        for node in nodes:
            if node.is_excluded:
                raise InvalidClipboardItemError(
                    path=directory.path,
                    item=node.urlpath
                    )
    else:
        raise InvalidClipboardModeError(path=directory.path, mode=mode)

    for node in nodes:
        try:
            paste_fnc(directory, node)
        except FileNotFoundError:
            raise MissingClipboardItemError(
                path=directory.path,
                item=node.urlpath
                )

    clipboard.clear()
    clipboard.to_response(response)
    return response


@actions.route('/clipboard/clear', defaults={'path': ''})
@actions.route('/clipboard/clear/<path:path>')
def clipboard_clear(path):
    response = redirect(url_for('browse', path=path))
    clipboard = Clipboard.from_request()
    clipboard.clear()
    clipboard.to_response(response)
    return response


@actions.errorhandler(FileActionsException)
def clipboard_error(e):
    file = Node(e.path) if hasattr(e, 'path') else None
    item = Node.from_urlpath(e.item) if hasattr(e, 'item') else None
    response = make_response((
        render_template(
            '400.file_actions.html',
            error=e, file=file, item=item
            ),
        400
        ))
    if isinstance(e, ClipboardException):
        clipboard = Clipboard.from_request()
        clipboard.clear()
        clipboard.to_response(response)
    return response


def register_plugin(manager):
    '''
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''
    def detect_upload(directory):
        return directory.is_directory and directory.can_upload

    def detect_clipboard(directory):
        return directory.is_directory and Clipboard.from_request()

    def excluded_clipboard(path):
        clipboard = Clipboard.from_request(request)
        if clipboard.mode == 'cut':
            base = manager.app.config['directory_base']
            return abspath_to_urlpath(path, base) in clipboard

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
        filter=lambda directory: directory.is_directory,
        text='Selection...',
        )
    manager.register_widget(
        place='header',
        type='html',
        html=lambda file: render_template(
            'widget.clipboard.file_actions.html',
            file=file,
            clipboard=Clipboard.from_request()
            ),
        filter=detect_clipboard,
        )
