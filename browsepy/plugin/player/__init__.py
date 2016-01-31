#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint, render_template

from .playable import PlayableFile, MetaPlayListFile, mimetypes

__basedir__= os.path.dirname(os.path.abspath(__file__))

player = Blueprint('player', __name__,
    url_prefix='/play',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )

@player.route('/audio/<path:path>')
def audio(path):
    f = PlayableFile.from_urlpath(path)
    return render_template('audio.player.html', file=f)

@player.route('/list/<path:path>')
def playlist(path):
    f = PlayListFile.from_urlpath(url)
    return render_template('list.player.html', file=f)

def detect_playable_mimetype(path, os_sep=os.sep):
    basename = path.rsplit(os_sep)[-1]
    if '.' in basename:
        ext = basename.rsplit('.')[-1]
        return mimetypes.get(ext, None)
    return None

def register_plugin(manager):
    '''
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''
    manager.register_blueprint(player)
    manager.register_mimetype_function(detect_playable_mimetype)

    style = manager.style_class('player.static', filename='css/browse.css')
    manager.register_widget(style)

    button_widget = manager.button_class(css='play')
    link_widget = manager.link_class()
    for widget in (link_widget, button_widget):
        manager.register_action(
            'player.audio',
            widget,
            mimetypes=(
                'audio/mpeg',
                'audio/ogg',
                'audio/wav',
            ))
        manager.register_action(
            'player.playlist',
            widget,
            mimetypes=(
                'audio/x-mpegurl', # m3u, m3u8
                'audio/x-scpls', # pls
            ))
