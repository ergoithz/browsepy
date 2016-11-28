#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint, render_template
from browsepy.file import File


mimetypes = {
    'mp3': 'audio/mpeg',
    'ogg': 'audio/ogg',
    'wav': 'audio/wav'
}

__basedir__ = os.path.dirname(os.path.abspath(__file__))

player = Blueprint(
    'deprecated_player', __name__,
    url_prefix='/play',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )


class PlayableFile(File):
    parent_class = File
    media_map = {
        'audio/mpeg': 'mp3',
        'audio/ogg': 'ogg',
        'audio/wav': 'wav',
    }

    def __init__(self, duration=None, title=None, **kwargs):
        self.duration = duration
        self.title = title
        super(PlayableFile, self).__init__(**kwargs)

    @property
    def title(self):
        return self._title or self.name

    @title.setter
    def title(self, title):
        self._title = title

    @property
    def media_format(self):
        return self.media_map[self.type]


@player.route('/audio/<path:path>')
def audio(path):
    f = PlayableFile.from_urlpath(path)
    return render_template('audio.player.html', file=f)


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

    style = manager.style_class(
        'deprecated_player.static',
        filename='css/browse.css'
        )
    manager.register_widget(style)

    button_widget = manager.button_class(css='play')
    link_widget = manager.link_class()
    for widget in (link_widget, button_widget):
        manager.register_action(
            'deprecated_player.audio',
            widget,
            mimetypes=(
                'audio/mpeg',
                'audio/ogg',
                'audio/wav',
            ))
