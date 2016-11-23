#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import unittest

import flask
import browsepy
import browsepy.manager
import browsepy.widget
import browsepy.manager as browsepy_manager

from .plugin import player as player


class ManagerMock(object):
    def __init__(self):
        self.blueprints = []
        self.mimetype_functions = []
        self.actions = []
        self.widgets = []

    def style_class(self, endpoint, **kwargs):
        return ('style', endpoint, kwargs)

    def button_class(self, *args, **kwargs):
        return ('button', args, kwargs)

    def javascript_class(self, endpoint, **kwargs):
        return ('javascript', endpoint, kwargs)

    def link_class(self, *args, **kwargs):
        return ('link', args, kwargs)

    def register_blueprint(self, blueprint):
        self.blueprints.append(blueprint)

    def register_mimetype_function(self, fnc):
        self.mimetype_functions.append(fnc)

    def register_widget(self, widget):
        self.widgets.append(widget)

    def register_action(self, blueprint, widget, mimetypes=(), **kwargs):
        self.actions.append((blueprint, widget, mimetypes, kwargs))


class FileMock(object):
    @property
    def type(self):
        return self.mimetype.split(';')[0]

    @property
    def category(self):
        return self.mimetype.split('/')[0]

    name = 'unnamed'

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestPlugins(unittest.TestCase):
    app_module = browsepy
    manager_module = browsepy.manager

    def setUp(self):
        self.app = self.app_module.app
        self.manager = self.manager_module.PluginManager(self.app)
        self.original_namespaces = self.app.config['plugin_namespaces']
        self.plugin_namespace, self.plugin_name = __name__.rsplit('.', 1)
        self.app.config['plugin_namespaces'] = (self.plugin_namespace,)

    def tearDown(self):
        self.app.config['plugin_namespaces'] = self.original_namespaces

    def test_manager(self):
        self.manager.load_plugin(self.plugin_name)
        self.assertTrue(self.manager._plugin_loaded)

        endpoints = sorted(
            action.endpoint
            for action in self.manager.get_actions(FileMock(mimetype='a/a'))
            )

        self.assertEqual(
            endpoints,
            sorted(('test_x_x', 'test_a_x', 'test_x_a', 'test_a_a')))
        self.assertEqual(
            self.app.view_functions['test_plugin.root'](),
            'test_plugin_root')
        self.assertIn('test_plugin', self.app.blueprints)

        self.assertRaises(
            self.manager_module.PluginNotFoundError,
            self.manager.load_plugin,
            'non_existent_plugin_module'
            )


def register_plugin(manager):
    widget_class = browsepy.widget.WidgetBase

    manager._plugin_loaded = True
    manager.register_action('test_x_x', widget_class('test_x_x'), ('*/*',))
    manager.register_action('test_a_x', widget_class('test_a_x'), ('a/*',))
    manager.register_action('test_x_a', widget_class('test_x_a'), ('*/a',))
    manager.register_action('test_a_a', widget_class('test_a_a'), ('a/a',))
    manager.register_action('test_b_x', widget_class('test_b_x'), ('b/*',))

    test_plugin_blueprint = flask.Blueprint(
        'test_old_api_plugin', __name__, url_prefix='/test_plugin_blueprint')
    test_plugin_blueprint.add_url_rule(
        '/', endpoint='root', view_func=lambda: 'test_plugin_root')

    manager.register_blueprint(test_plugin_blueprint)


class TestPlayerBase(unittest.TestCase):
    module = player

    def setUp(self):
        self.app = flask.Flask(self.__class__.__name__)
        self.manager = ManagerMock()


class TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        self.module.register_plugin(self.manager)

        self.assertIn(self.module.player, self.manager.blueprints)
        self.assertIn(
            self.module.detect_playable_mimetype,
            self.manager.mimetype_functions)

        widgets = [action[1] for action in self.manager.widgets]
        self.assertIn('player.static', widgets)

        widgets = [action[2] for action in self.manager.widgets]
        self.assertIn({'filename': 'css/browse.css'}, widgets)

        actions = [action[0] for action in self.manager.actions]
        self.assertIn('player.audio', actions)


class TestIntegrationBase(TestPlayerBase):
    player_module = player
    browsepy_module = browsepy
    manager_module = browsepy_manager


class TestIntegration(TestIntegrationBase):
    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['plugin_namespaces'] = (
            'browsepy.tests.deprecated.plugin',
            )
        self.manager = self.manager_module.PluginManager(self.app)
        self.manager.load_plugin('player')
        self.assertIn(self.player_module.player, self.app.blueprints.values())


class TestPlayable(TestIntegrationBase):
    module = player

    def setUp(self):
        super(TestIntegrationBase, self).setUp()
        self.manager = self.manager_module.MimetypeActionPluginManager(
            self.app)
        self.manager.register_mimetype_function(
            self.player_module.detect_playable_mimetype)

    def test_playablefile(self):
        exts = {
         'mp3': 'mp3',
         'wav': 'wav',
         'ogg': 'ogg'
        }
        for ext, media_format in exts.items():
            pf = self.module.PlayableFile(path='asdf.%s' % ext, app=self.app)
            self.assertEqual(pf.media_format, media_format)


if __name__ == '__main__':
    unittest.main()
