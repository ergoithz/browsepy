#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import unittest

import flask
import browsepy
import browsepy.manager
import browsepy.widget


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


if __name__ == '__main__':
    unittest.main()
