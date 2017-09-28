#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import shutil

from flask import Blueprint, render_template, request, redirect, url_for
from werkzeug.exceptions import NotFound

from browsepy import get_cookie_browse_sorting, browse_sortkey_reverse
from browsepy.file import Node
from browsepy.compat import map
from browsepy.exceptions import OutsideDirectoryBase

from .clipboard import Clipboard


__basedir__ = os.path.dirname(os.path.abspath(__file__))

actions = Blueprint(
    'file_actions',
    __name__,
    url_prefix='/file-actions',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
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
        return render_template('create_directory.html', file=directory)

    os.mkdir(os.path.join(directory.path, request.form['name']))

    return redirect(url_for('browse', path=directory.urlpath))


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
        'clipboard.html',
        file=directory,
        clipboard=clipboard,
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
    excluded = manager.app.config.get('exclude_fnc')
    manager.app.config['exclude_fnc'] = (
        Clipboard.excluded
        if not excluded else
        lambda path: Clipboard.excluded(path) or excluded(path)
        )
    manager.register_blueprint(actions)
    manager.register_widget(
        place='styles',
        type='stylesheet',
        endpoint='file_actions.static',
        filename='clipboard.css',
        filter=Clipboard.detect_selection,
        )
    manager.register_widget(
        place='scripts',
        type='script',
        endpoint='file_actions.static',
        filename='clipboard.js',
        filter=Clipboard.detect_selection,
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.create_directory',
        text='Create directory',
        filter=lambda file: file.can_upload,
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.clipboard',
        text=lambda file: (
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
        filter=Clipboard.detect_target,
        )
    manager.register_widget(
        place='header',
        type='button',
        endpoint='file_actions.clipboard_clear',
        text='Clear',
        filter=Clipboard.detect,
        )
