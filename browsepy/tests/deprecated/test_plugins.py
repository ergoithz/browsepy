#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import unittest

import flask
import browsepy
import browsepy.file as browsepy_file
import browsepy.widget as browsepy_widget
import browsepy.manager as browsepy_manager

from browsepy.tests.deprecated.plugin import player as player


class ManagerMock(object):
    def __init__(self):
        self.blueprints = []
        self.mimetype_functions = []
        self.actions = []
        self.widgets = []

    @staticmethod
    def style_class(endpoint, **kwargs):
        return ('style', endpoint, kwargs)

    @staticmethod
    def button_class(*args, **kwargs):
        return ('button', args, kwargs)

    @staticmethod
    def javascript_class(endpoint, **kwargs):
        return ('javascript', endpoint, kwargs)

    @staticmethod
    def link_class(*args, **kwargs):
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

    is_directory = False
    name = 'unnamed'

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestPlugins(unittest.TestCase):
    app_module = browsepy
    manager_module = browsepy_manager

    def setUp(self):
        self.app = self.app_module.app
        self.manager = self.manager_module.PluginManager(self.app)
        self.original_namespaces = self.app.config['plugin_namespaces']
        self.plugin_namespace, self.plugin_name = __name__.rsplit('.', 1)
        self.app.config['plugin_namespaces'] = (self.plugin_namespace,)

    def tearDown(self):
        self.app.config['plugin_namespaces'] = self.original_namespaces
        self.manager.clear()

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
            self.app.view_functions['old_test_plugin.root'](),
            'old_test_plugin')
        self.assertIn('old_test_plugin', self.app.blueprints)

        self.assertRaises(
            self.manager_module.PluginNotFoundError,
            self.manager.load_plugin,
            'non_existent_plugin_module'
            )


def register_plugin(manager):
    widget_class = browsepy_widget.WidgetBase

    manager._plugin_loaded = True
    manager.register_action('test_x_x', widget_class('test_x_x'), ('*/*',))
    manager.register_action('test_a_x', widget_class('test_a_x'), ('a/*',))
    manager.register_action('test_x_a', widget_class('test_x_a'), ('*/a',))
    manager.register_action('test_a_a', widget_class('test_a_a'), ('a/a',))
    manager.register_action('test_b_x', widget_class('test_b_x'), ('b/*',))

    test_plugin_blueprint = flask.Blueprint(
        'old_test_plugin', __name__, url_prefix='/old_test_plugin_blueprint')
    test_plugin_blueprint.add_url_rule(
        '/', endpoint='root', view_func=lambda: 'old_test_plugin')

    manager.register_blueprint(test_plugin_blueprint)


class TestPlayerBase(unittest.TestCase):
    module = player
    scheme = 'test'
    hostname = 'testing'
    urlprefix = '%s://%s' % (scheme, hostname)

    def assertUrlEqual(self, a, b):
        self.assertIn(a, (b, '%s%s' % (self.urlprefix, b)))

    def setUp(self):
        self.app = flask.Flask(self.__class__.__name__)
        self.app.config['directory_remove'] = None
        self.app.config['SERVER_NAME'] = self.hostname
        self.app.config['PREFERRED_URL_SCHEME'] = self.scheme
        self.manager = ManagerMock()


class TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        self.module.register_plugin(self.manager)

        self.assertIn(self.module.player, self.manager.blueprints)
        self.assertIn(
            self.module.detect_playable_mimetype,
            self.manager.mimetype_functions)

        widgets = [action[1] for action in self.manager.widgets]
        self.assertIn('deprecated_player.static', widgets)

        widgets = [action[2] for action in self.manager.widgets]
        self.assertIn({'filename': 'css/browse.css'}, widgets)

        actions = [action[0] for action in self.manager.actions]
        self.assertIn('deprecated_player.audio', actions)


class TestIntegrationBase(TestPlayerBase):
    player_module = player
    browsepy_module = browsepy
    manager_module = browsepy_manager
    widget_module = browsepy_widget
    file_module = browsepy_file


class TestIntegration(TestIntegrationBase):
    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config.update(
            SERVER_NAME=self.hostname,
            PREFERRED_URL_SCHEME=self.scheme,
            plugin_namespaces=('browsepy.tests.deprecated.plugin',)
        )
        manager = self.manager_module.PluginManager(self.app)
        manager.load_plugin('player')
        self.assertIn(self.player_module.player, self.app.blueprints.values())

    def test_register_action(self):
        manager = self.manager_module.MimetypeActionPluginManager(self.app)
        widget = self.widget_module.WidgetBase()  # empty
        manager.register_action('browse', widget, mimetypes=('*/*',))
        actions = manager.get_actions(FileMock(mimetype='text/plain'))
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].widget, widget)
        manager.register_action('browse', widget, mimetypes=('text/*',))
        actions = manager.get_actions(FileMock(mimetype='text/plain'))
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[1].widget, widget)
        manager.register_action('browse', widget, mimetypes=('text/plain',))
        actions = manager.get_actions(FileMock(mimetype='text/plain'))
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[2].widget, widget)
        widget = self.widget_module.ButtonWidget()
        manager.register_action('browse', widget, mimetypes=('text/plain',))
        actions = manager.get_actions(FileMock(mimetype='text/plain'))
        self.assertEqual(len(actions), 4)
        self.assertEqual(actions[3].widget, widget)
        widget = self.widget_module.LinkWidget()
        manager.register_action('browse', widget, mimetypes=('*/plain',))
        actions = manager.get_actions(FileMock(mimetype='text/plain'))
        self.assertEqual(len(actions), 5)
        self.assertNotEqual(actions[4].widget, widget)
        widget = self.widget_module.LinkWidget(icon='file', text='something')
        manager.register_action('browse', widget, mimetypes=('*/plain',))
        actions = manager.get_actions(FileMock(mimetype='text/plain'))
        self.assertEqual(len(actions), 6)
        self.assertEqual(actions[5].widget, widget)

    def test_register_widget(self):
        file = self.file_module.Node()
        manager = self.manager_module.MimetypeActionPluginManager(self.app)
        widget = self.widget_module.StyleWidget('static', filename='a.css')
        manager.register_widget(widget)
        widgets = manager.get_widgets('style')
        self.assertEqual(len(widgets), 1)
        self.assertIsInstance(widgets[0], self.widget_module.StyleWidget)
        self.assertEqual(widgets[0], widget)

        widgets = manager.get_widgets(place='style')
        self.assertEqual(len(widgets), 1)
        self.assertIsInstance(widgets[0], self.widget_module.StyleWidget)
        self.assertEqual(widgets[0], widget)

        widgets = manager.get_widgets(file=file, place='styles')
        self.assertEqual(len(widgets), 1)
        self.assertIsInstance(widgets[0], manager.widget_types['stylesheet'])
        self.assertUrlEqual(widgets[0].href, '/static/a.css')

        widget = self.widget_module.JavascriptWidget('static', filename='a.js')
        manager.register_widget(widget)
        widgets = manager.get_widgets('javascript')
        self.assertEqual(len(widgets), 1)
        self.assertIsInstance(widgets[0], self.widget_module.JavascriptWidget)
        self.assertEqual(widgets[0], widget)

        widgets = manager.get_widgets(place='javascript')
        self.assertEqual(len(widgets), 1)
        self.assertIsInstance(widgets[0], self.widget_module.JavascriptWidget)
        self.assertEqual(widgets[0], widget)

        widgets = manager.get_widgets(file=file, place='scripts')
        self.assertEqual(len(widgets), 1)
        self.assertIsInstance(widgets[0], manager.widget_types['script'])
        self.assertUrlEqual(widgets[0].src, '/static/a.js')

    def test_for_file(self):
        manager = self.manager_module.MimetypeActionPluginManager(self.app)
        widget = self.widget_module.LinkWidget(icon='asdf', text='something')
        manager.register_action('browse', widget, mimetypes=('*/plain',))
        file = self.file_module.File('asdf.txt', plugin_manager=manager,
                                     app=self.app)
        self.assertEqual(file.link.icon, 'asdf')
        self.assertEqual(file.link.text, 'something')

        widget = self.widget_module.LinkWidget()
        manager.register_action('browse', widget, mimetypes=('*/plain',))
        file = self.file_module.File('asdf.txt', plugin_manager=manager,
                                     app=self.app)
        self.assertEqual(file.link.text, 'asdf.txt')

    def test_from_file(self):
        file = self.file_module.File('asdf.txt')
        widget = self.widget_module.LinkWidget.from_file(file)
        self.assertEqual(widget.text, 'asdf.txt')


class TestPlayable(TestIntegrationBase):
    module = player

    def setUp(self):
        super(TestPlayable, self).setUp()
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
