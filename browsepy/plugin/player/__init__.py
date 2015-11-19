#!/usr/bin/env python
# -*- coding: UTF-8 -*-

def play(path):
    return 'asdf'

def load_actions(register):
    register(
        '/play/<path:path>',
        '&#9658;',
        view_func=play,
        mimetypes=(
            'audio/mpeg',
            'audio/mp4',
            'audio/ogg',
            'audio/webm',
            'audio/wav',
            'video/mpeg',
            'video/mp4',
            'video/ogg',
            'video/ogv',
            'video/webm',
        ))
