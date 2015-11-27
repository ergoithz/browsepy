#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint, render_template, current_app, url_for

from browsepy.file import File

__basedir__= os.path.dirname(os.path.abspath(__file__))

player = Blueprint('player', __name__,
    url_prefix='/play',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )

media_map = {
    'audio/mpeg': 'mp3',
    'audio/mp4': 'mp4',
    'audio/ogg': 'ogg',
    'audio/webm': 'webm',
    'audio/wav': 'wav',

    'video/mpeg': 'mp4',
    'video/mp4': 'mp4',
    'video/ogg': 'ogg',
    'video/ogv': 'ogg',
    'video/webm': 'webm',
}

@player.route('/audio/<path:path>')
def audio(path):
    f = File.from_urlpath(path)
    m = media_map[f.type]
    return render_template('audio.player.html', file=f, directory=f, media_format=m)

@player.route('/video/<path:path>')
def video(path):
    return render_template('video.player.html')

@player.route('/list/<path:path>')
def playlist(path):
    return render_template('list.player.html')

def register_plugin(manager):
    manager.register_blueprint(player)

    style = manager.style_class('player.static', filename='css/browse.css')
    manager.register_widget(style)
    
    widget = manager.button_class(css='play')
    manager.register_action(
        'player.audio',
        widget,
        mimetypes=(
            'audio/mpeg',
            'audio/mp4',
            'audio/ogg',
            'audio/webm',
            'audio/wav',
        ))
    manager.register_action(
        'player.video',
        widget,
        mimetypes=(
            'video/mpeg',
            'video/mp4',
            'video/ogg',
            'video/ogv',
            'video/webm',
        ))
    manager.register_action(
        'player.playlist',
        widget,
        mimetypes=(
            'audio/x-mpegurl', # m3u, m3u8
            'audio/x-scpls', # pls
        ))
