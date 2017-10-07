import unittest
import tempfile
import shutil
import os
import os.path

import bs4
import flask

from werkzeug.utils import cached_property

import browsepy.plugin.file_actions as file_actions
import browsepy.manager as browsepy_manager
import browsepy


class Page(object):
    def __init__(self, source):
        self.tree = bs4.BeautifulSoup(source, 'html.parser')

    @cached_property
    def urlpath(self):
        return self.tree.h1.find('ol', class_='path').get_text().strip()

    @cached_property
    def action(self):
        return self.tree.h2.get_text().strip()

    @cached_property
    def entries(self):
        rows = self.tree.find('table', class_='browser').find_all('tr')
        return {
            r('td')[2].get_text(): r.input['value']
            for r in rows
            }


class TestIntegration(unittest.TestCase):
    actions_module = file_actions
    browsepy_module = browsepy
    manager_module = browsepy_manager

    def setUp(self):
        self.base = 'c:\\base' if os.name == 'nt' else '/base'
        self.app = flask.Flask(self.__class__.__name__)
        self.app.config.update(
            directory_base=self.base,
            exclude_fnc=None,
            )

    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['plugin_namespaces'] = ('browsepy.plugin',)
        manager = self.manager_module.PluginManager(self.app)
        manager.load_plugin('file-actions')
        self.assertIn(
            self.actions_module.actions,
            self.app.blueprints.values()
            )

    def test_reload(self):
        self.app.config.update(
            plugin_modules=[],
            plugin_namespaces=[]
            )
        manager = self.manager_module.PluginManager(self.app)
        self.assertNotIn(
            self.actions_module.actions,
            self.app.blueprints.values()
            )
        self.app.config.update(
            plugin_modules=['file-actions'],
            plugin_namespaces=['browsepy.plugin']
            )
        manager.reload()
        self.assertIn(
            self.actions_module.actions,
            self.app.blueprints.values()
            )


class TestAction(unittest.TestCase):
    module = file_actions

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.basename = os.path.basename(self.base)
        self.app = flask.Flask('browsepy')
        self.app.register_blueprint(self.module.actions)
        self.app.config.update(
            directory_base=self.base,
            directory_upload=self.base,
            directory_remove=self.base,
            exclude_fnc=None,
            use_binary_multiples=True,
            )
        self.app.add_url_rule(
            '/browse/<path:path>',
            endpoint='browse',
            view_func=lambda path: None
            )

    def tearDown(self):
        shutil.rmtree(self.base)

    def mkdir(self, *path):
        os.mkdir(os.path.join(self.base, *path))

    def touch(self, *path):
        open(os.path.join(self.base, *path), 'w').close()

    def assertExist(self, *path):
        abspath = os.path.join(self.base, *path)
        self.assertTrue(
            os.path.exists(abspath),
            'File %s does not exist.' % abspath
            )

    def assertNotExist(self, *path):
        abspath = os.path.join(self.base, *path)
        self.assertFalse(
            os.path.exists(abspath),
            'File %s does exist.' % abspath
            )

    def test_create_directory(self):
        with self.app.test_client() as client:
            response = client.get('/file-actions/create/directory')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertEqual(page.urlpath, self.basename)

            response = client.post(
                '/file-actions/create/directory',
                data={
                    'name': 'asdf'
                    })
            self.assertEqual(response.status_code, 302)
            self.assertExist('asdf')

    def test_selection(self):
        self.touch('a')
        self.touch('b')
        with self.app.test_client() as client:
            response = client.get('/file-actions/clipboard')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertEqual(page.urlpath, self.basename)
            self.assertIn('a', page.entries)
            self.assertIn('b', page.entries)

    def test_copy(self):
        files = ['a', 'b']
        for p in files:
            self.touch(p)
        with self.app.test_client() as client:
            response = client.post(
                '/file-actions/clipboard',
                data={
                    'path': files,
                    'mode-cut': 'something',
                    })
            self.assertEqual(response.status_code, 302)

            self.mkdir('c')
            response = client.get(
                '/file-actions/clipboard/paste/c'
                )
            self.assertEqual(response.status_code, 302)

            for p in files:
                self.assertNotExist(p)

            for p in files:
                self.assertExist('c', p)
