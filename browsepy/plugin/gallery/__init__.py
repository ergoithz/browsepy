#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os.path

from flask import Blueprint, render_template, jsonify, url_for
from werkzeug.exceptions import NotFound

from browsepy import stream_template, get_cookie_browse_sorting, \
                     browse_sortkey_reverse
from browsepy.file import OutsideDirectoryBase

from .images import ImageFile, ImageDirectory, \
                       detect_image_mimetype
from ... import open_file   

__basedir__ = os.path.dirname(os.path.abspath(__file__))

gallery = Blueprint(
    'gallery',
    __name__,
    url_prefix='/gallery',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )


@gallery.route('/image/<path:path>')
def image(path):
    try:
        file = ImageFile.from_urlpath(path)
        if file.is_file:
            curdir = ImageDirectory.from_urlpath(os.path.dirname(path))
            return stream_template(
                'gallery.html',
                file=file,
                curdir=curdir
                )

    except OutsideDirectoryBase:
        pass
    return NotFound()


@gallery.route("/dirlist", defaults={"path": ""})
@gallery.route('/dirlist/<path:path>')
def directory_json(path):
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)
    try:
        file = ImageDirectory.from_urlpath(path)
        return jsonify([dict(url=url_for("open", path=e.urlpath),
                             caption=e.title,
                             thumbnail=url_for("open", path=e.urlpath)) for e in sorted(file.entries(), key=lambda x: x.title) if isinstance(e, ImageFile)])
    except OutsideDirectoryBase:
        pass
    return NotFound()

@gallery.route("/directory", defaults={"path": ""})
@gallery.route('/directory/<path:path>')
def directory(path):
    sort_property = get_cookie_browse_sorting(path, 'text')
    sort_fnc, sort_reverse = browse_sortkey_reverse(sort_property)
    try:
        file = ImageDirectory.from_urlpath(path)
        if file.is_directory:
            return stream_template(
                'gallery.html',
                file=file,
                sort_property=sort_property,
                sort_fnc=sort_fnc,
                sort_reverse=sort_reverse,
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
    # manager.register_argument(
    #     '--player-directory-play', action='store_false',
    #     help='enable directories as playlist'
    #     )


def register_plugin(manager):
    '''
    Register blueprints and actions using given plugin manager.

    :param manager: plugin manager
    :type manager: browsepy.manager.PluginManager
    '''
    manager.register_blueprint(gallery)
    manager.register_mimetype_function(detect_image_mimetype)

    # add style tag
    manager.register_widget(
        place='styles',
        type='stylesheet',
        endpoint='gallery.static',
        filename='css/browse.css'
    )

    # register link actions
    manager.register_widget(
        place='entry-link',
        type='link',
        endpoint='gallery.image',
        filter=ImageFile.detect
    )
 

    # register action buttons
    manager.register_widget(
        place='entry-actions',
        css='showimage',
        type='button',
        endpoint='gallery.image',
        filter=ImageFile.detect
    )

    manager.register_widget(
        place='header',
        type='button',
        endpoint='gallery.directory',
        text='Show directory',
        filter=ImageDirectory.detect
        )
