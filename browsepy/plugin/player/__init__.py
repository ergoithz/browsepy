#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint

__basedir__= os.path.dirname(os.path.abspath(__file__))

player = Blueprint('player', __name__,
    url_prefix='/play',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )
    
@player.route('/audio/<path:path>')
def audio(path):
    return 'audio'
    
@player.route('/video/<path:path>')
def video(path):
    return 'video'
    
@player.route('/list/<path:path>')
def playlist(path):
    return 'list'
    
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