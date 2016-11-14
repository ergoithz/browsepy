#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint, render_template
from werkzeug.exceptions import NotFound

from browsepy import stream_template
from browsepy.file import OutsideDirectoryBase

from .playable import PlayableFile, PlayableDirectory, \
                      PlayListFile, detect_playable_mimetype


__basedir__ = os.path.dirname(os.path.abspath(__file__))

player = Blueprint(
    'player',
    __name__,
    url_prefix='/play',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )


@player.route('/audio/<path:path>')
def audio(path):
    try:
        file = PlayableFile.from_urlpath(path)
        if file.is_file:
            return render_template('audio.player.html', file=file)
    except OutsideDirectoryBase:
        pass
    return NotFound()


@player.route('/list/<path:path>')
def playlist(path):
    try:
        file = PlayListFile.from_urlpath(path)
        if file.is_file:
            return stream_template(
                'audio.player.html',
                file=file,
                playlist=True
                )
    except OutsideDirectoryBase:
        pass
    return NotFound()


@player.route("/directory", defaults={"path": ""})
@player.route('/directory/<path:path>')
def directory(path):
    try:
        file = PlayableDirectory.from_urlpath(path)
        if file.is_directory:
            return stream_template(
                'audio.player.html',
                file=file,
                playlist=True
                )
    except OutsideDirectoryBase:
        pass
    return NotFound()


def register_arguments(manager):
    '''
    Register arguments using given plugin manager.

    This method is called before `register_plugin`.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''

    # Arguments are forwarded to argparse:ArgumentParser.add_argument,
    # https://docs.python.org/3.7/library/argparse.html#the-add-argument-method
    manager.register_argument(
        '--player-directory-play', action='store_true',
        help='enable directories as playlist'
        )


def register_plugin(manager):
    '''
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''
    manager.register_blueprint(player)
    manager.register_mimetype_function(detect_playable_mimetype)

    # add style tag
    manager.register_widget(
        place='styles',
        type='stylesheet',
        endpoint='player.static',
        filename='css/browse.css'
    )

    # register link actions
    manager.register_widget(
        place='entry-link',
        type='link',
        endpoint='player.audio',
        filter=PlayableFile.detect
    )
    manager.register_widget(
        place='entry-link',
        icon='playlist',
        type='link',
        endpoint='player.playlist',
        filter=PlayListFile.detect
    )

    # register action buttons
    manager.register_widget(
        place='entry-actions',
        css='play',
        type='button',
        endpoint='player.audio',
        filter=PlayableFile.detect
    )
    manager.register_widget(
        place='entry-actions',
        css='play',
        type='button',
        endpoint='player.playlist',
        filter=PlayListFile.detect
    )

    # check argument (see `register_arguments`) before registering
    if manager.get_argument('player_directory_play'):
        # register header button
        manager.register_widget(
            place='header',
            type='button',
            endpoint='player.directory',
            text='Play directory',
            filter=PlayableDirectory.detect
            )
