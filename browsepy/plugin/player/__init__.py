#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint, render_template, current_app

from browsepy import urlpath_to_abspath
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
    f = File(urlpath_to_abspath(path, current_app.config['directory_base']))
    m = media_map[f.type]
    return render_template('audio.player.html', file=f, media_format=m)

@player.route('/video/<path:path>')
def video(path):
    return render_template('video.player.html')

@player.route('/list/<path:path>')
def playlist(path):
    return render_template('list.player.html')

def load_blueprints(manager):
    manager.register_blueprint(player)

def load_actions(manager):
    manager.register_action(
        endpoint='player.audio',
        text='&#9658;',
        mimetypes=(
            'audio/mpeg',
            'audio/mp4',
            'audio/ogg',
            'audio/webm',
            'audio/wav',
        ))
    manager.register_action(
        endpoint='player.video',
        text='&#9658;',
        mimetypes=(
            'video/mpeg',
            'video/mp4',
            'video/ogg',
            'video/ogv',
            'video/webm',
        ))
    manager.register_action(
        endpoint='player.playlist',
        text='&#9658;',
        mimetypes=(
            'audio/x-mpegurl', # m3u, m3u8
            'audio/x-scpls', # pls
        ))
