
import unittest
import flask

import browsepy
import browsepy.manager
import browsepy.tests.utils as test_utils

from browsepy.plugin.player.tests import *  # noqa


class FileMock(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestMimetypePluginManager(unittest.TestCase):
    module = browsepy.manager

    def test_mimetype(self):
        manager = self.module.MimetypePluginManager()
        self.assertEqual(
            manager.get_mimetype('potato'),
            'application/octet-stream'
            )
        self.assertEqual(
            manager.get_mimetype('potato.txt'),
            'text/plain'
            )
        manager.register_mimetype_function(
            lambda x: 'application/xml' if x == 'potato' else None
            )
        self.assertEqual(
            manager.get_mimetype('potato.txt'),
            'text/plain'
            )
        self.assertEqual(
            manager.get_mimetype('potato'),
            'application/xml'
            )


class TestPlugins(unittest.TestCase):
    app_module = browsepy
    manager_module = browsepy.manager

    def setUp(self):
        self.app = self.app_module.app
        self.original_namespaces = self.app.config['plugin_namespaces']
        self.plugin_namespace, self.plugin_name = __name__.rsplit('.', 1)
        self.app.config['plugin_namespaces'] = (self.plugin_namespace,)
        self.manager = self.manager_module.PluginManager(self.app)

    def tearDown(self):
        self.app.config['plugin_namespaces'] = self.original_namespaces
        self.manager.clear()
        test_utils.clear_flask_context()

    def test_manager(self):
        self.manager.load_plugin(self.plugin_name)
        self.assertTrue(self.manager._plugin_loaded)

        endpoints = sorted(
            action.endpoint
            for action in self.manager.get_widgets(FileMock(mimetype='a/a'))
            )

        self.assertEqual(
            endpoints,
            sorted(('test_x_x', 'test_a_x', 'test_x_a', 'test_a_a'))
            )
        self.assertEqual(
            self.app.view_functions['test_plugin.root'](),
            'test_plugin_root'
            )
        self.assertIn('test_plugin', self.app.blueprints)

        self.assertRaises(
            self.manager_module.PluginNotFoundError,
            self.manager.load_plugin,
            'non_existent_plugin_module'
            )

        self.assertRaises(
            self.manager_module.InvalidArgumentError,
            self.manager.register_widget
        )

    def test_namespace_prefix(self):
        self.assertTrue(self.manager.import_plugin(self.plugin_name))
        self.app.config['plugin_namespaces'] = (
            self.plugin_namespace + '.test_',
            )
        self.assertTrue(self.manager.import_plugin('module'))


def register_plugin(manager):
    manager._plugin_loaded = True
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_x_x',
        filter=lambda f: True
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_a_x',
        filter=lambda f: f.mimetype.startswith('a/')
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_x_a',
        filter=lambda f: f.mimetype.endswith('/a')
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_a_a',
        filter=lambda f: f.mimetype == 'a/a'
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_b_x',
        filter=lambda f: f.mimetype.startswith('b/')
        )

    test_plugin_blueprint = flask.Blueprint(
        'test_plugin',
        __name__,
        url_prefix='/test_plugin_blueprint')
    test_plugin_blueprint.add_url_rule(
        '/',
        endpoint='root',
        view_func=lambda: 'test_plugin_root')

    manager.register_blueprint(test_plugin_blueprint)
