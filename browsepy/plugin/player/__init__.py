#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path
import codecs
import mimetypes

from flask import Blueprint, render_template, current_app, url_for

from browsepy.file import File, check_under_base

from .playable import PlayableFile, mimetypes

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
    manager.register_blueprint(player)
    manager.register_mimetype_function(detect_playable_mimetype)

    style = manager.style_class('player.static', filename='css/browse.css')
    manager.register_widget(style)

    widget = manager.button_class(css='play')
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
