#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import shutil

from flask import Blueprint, render_template, request, redirect, url_for
from werkzeug.exceptions import NotFound

from browsepy import get_cookie_browse_sorting, browse_sortkey_reverse
from browsepy.file import Node, abspath_to_urlpath, secure_filename, \
                          current_restricted_chars, common_path_separators
from browsepy.compat import map, re_escape
from browsepy.exceptions import OutsideDirectoryBase, InvalidFilenameError

from .clipboard import Clipboard


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
        raise InvalidFilenameError(
            path=directory.path,
            filename=basename,
            )

    os.mkdir(os.path.join(directory.path, basename))

    return redirect(url_for('browse', file=directory))


@actions.route('/clipboard', methods=('GET', 'POST'), defaults={'path': ''})
@actions.route('/clipboard/<path:path>', methods=('GET', 'POST'))
def clipboard(path):
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)

    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if directory.is_excluded or not directory.is_directory:
        return NotFound()

    if request.method == 'POST':
        mode = 'cut' if request.form.get('mode-cut') else 'copy'
        response = redirect(url_for('browse', path=directory.urlpath))
        clipboard = Clipboard(request.form.getlist('path'), mode)
        clipboard.to_response(response)
        return response

    clipboard = Clipboard.from_request()
    clipboard.mode = 'select'  # disables exclusion
    return render_template(
        'clipboard.file_actions.html',
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
    try:
        directory = Node.from_urlpath(path)
    except OutsideDirectoryBase:
        return NotFound()

    if (
      not directory.is_directory or
      directory.is_excluded or
      not directory.can_upload
      ):
        return NotFound()

    response = redirect(url_for('browse', path=directory.urlpath))
    clipboard = Clipboard.from_request()
    cut = clipboard.mode == 'cut'
    clipboard.mode = 'paste'  # disables exclusion

    for node in map(Node.from_urlpath, clipboard):
        if not node.is_excluded:
            if not cut:
                if node.is_directory:
                    shutil.copytree(node.path, directory.path)
                else:
                    shutil.copy2(node.path, directory.path)
            elif node.parent.can_remove:
                shutil.move(node.path, directory.path)

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


def register_plugin(manager):
    '''
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''
    def detect_selection(directory):
        return (
            directory.is_directory and
            Clipboard.from_request().mode == 'select'
            )

    def detect_upload(directory):
        return directory.is_directory and directory.can_upload

    def detect_target(directory):
        return detect_upload(directory) and detect_clipboard(directory)

    def detect_clipboard(directory):
        return directory.is_directory and Clipboard.from_request()

    def excluded_clipboard(path):
        clipboard = Clipboard.from_request(request)
        if clipboard.mode == 'cut':
            base = manager.app.config['directory_base']
            return abspath_to_urlpath(path, base) in clipboard

    excluded = manager.app.config.get('exclude_fnc')
    manager.app.config['exclude_fnc'] = (
        excluded_clipboard
        if not excluded else
        lambda path: excluded_clipboard(path) or excluded(path)
        )
    manager.register_blueprint(actions)
    manager.register_widget(
        place='styles',
        type='stylesheet',
        endpoint='file_actions.static',
        filename='style.css',
        filter=detect_selection,
        )
    manager.register_widget(
        place='scripts',
        type='script',
        endpoint='file_actions.static',
        filename='script.js',
        filter=detect_selection,
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
        endpoint='file_actions.clipboard',
        filter=lambda directory: directory.is_directory,
        text=lambda directory: (
            'Selection ({})...'.format(Clipboard.count())
            if Clipboard.count() else
            'Selection...'
            ),
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.clipboard_paste',
        text='Paste here',
        filter=detect_target,
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.clipboard_clear',
        text='Clear',
        filter=detect_clipboard,
        )
