import unittest
import tempfile
import shutil
import os
import os.path
import functools

import bs4
import flask

from werkzeug.utils import cached_property

import browsepy.plugin.file_actions as file_actions
import browsepy.plugin.file_actions.clipboard as file_actions_clipboard
import browsepy.manager as browsepy_manager
import browsepy.exceptions as browsepy_exceptions
import browsepy


class CookieProxy(object):
    def __init__(self, client):
        self._client = client

    @property
    def cookies(self):
        return {
            cookie.name: cookie.value for cookie in self._client.cookie_jar
            }

    def set_cookie(self, name, value, **kwargs):
        return self._client.set_cookie(
            self._client.environ_base['REMOTE_ADDR'], name, value, **kwargs)


class Page(object):
    def __init__(self, source):
        self.tree = bs4.BeautifulSoup(source, 'html.parser')

    @cached_property
    def widgets(self):
        header = self.tree.find('header')
        return [
            (r.name, r[attr])
            for (source, attr) in (
                (header.find_all('a'), 'href'),
                (header.find_all('link', rel='stylesheet'), 'href'),
                (header.find_all('script'), 'src'),
                (header.find_all('form'), 'action'),
                )
            for r in source
            ]

    @cached_property
    def urlpath(self):
        return self.tree.h1.find('ol', class_='path').get_text().strip()

    @cached_property
    def action(self):
        return self.tree.h2.get_text().strip()

    @cached_property
    def entries(self):
        table = self.tree.find('table', class_='browser')
        return {} if not table else {
            r('td')[1].get_text(): r.input['value'] if r.input else r.a['href']
            for r in table.find('tbody').find_all('tr')
            }

    @cached_property
    def selected(self):
        table = self.tree.find('table', class_='browser')
        return {} if not table else {
            r('td')[1].get_text(): i['value']
            for r in table.find('tbody').find_all('tr')
            for i in r.find_all('input', selected=True)
            }


class TestRegistration(unittest.TestCase):
    actions_module = file_actions
    manager_module = browsepy_manager
    browsepy_module = browsepy

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


class TestIntegration(unittest.TestCase):
    actions_module = file_actions
    manager_module = browsepy_manager
    browsepy_module = browsepy
    clipboard_module = file_actions_clipboard

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.app = self.browsepy_module.app
        self.app.config.update(
            directory_base=self.base,
            directory_start=self.base,
            directory_upload=None,
            exclude_fnc=None,
            plugin_modules=['file-actions'],
            plugin_namespaces=[
                'browsepy.plugin'
                ]
            )
        self.manager = self.app.extensions['plugin_manager']
        self.manager.reload()

    def tearDown(self):
        shutil.rmtree(self.base)
        self.app.config['plugin_modules'] = []
        self.manager.clear()

    def test_detection(self):
        with self.app.test_client() as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)

            url = functools.partial(flask.url_for, path='')

            page = Page(response.data)
            with self.app.app_context():
                self.assertIn(
                    ('a', url('file_actions.selection')),
                    page.widgets
                    )

                self.assertNotIn(
                    ('a', url('file_actions.clipboard_paste')),
                    page.widgets
                    )

            proxy = CookieProxy(client)
            clipboard = self.clipboard_module.Clipboard.from_request(proxy)
            clipboard.mode = 'copy'
            clipboard.add('whatever')
            clipboard.to_response(proxy, proxy)

            response = client.get('/')
            self.assertEqual(response.status_code, 200)

            page = Page(response.data)
            with self.app.app_context():
                self.assertIn(
                    ('a', url('file_actions.selection')),
                    page.widgets
                    )
                self.assertNotIn(
                    ('a', url('file_actions.clipboard_paste')),
                    page.widgets
                    )
                self.assertIn(
                    ('a', url('file_actions.clipboard_clear')),
                    page.widgets
                    )

            self.app.config['directory_upload'] = self.base
            response = client.get('/')
            self.assertEqual(response.status_code, 200)

            page = Page(response.data)
            with self.app.app_context():
                self.assertIn(
                    ('a', url('file_actions.selection')),
                    page.widgets
                    )
                self.assertIn(
                    ('a', url('file_actions.clipboard_paste')),
                    page.widgets
                    )
                self.assertIn(
                    ('a', url('file_actions.clipboard_clear')),
                    page.widgets
                    )

    def test_exclude(self):
        open(os.path.join(self.base, 'potato'), 'w').close()
        with self.app.test_client() as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)

            page = Page(response.data)
            self.assertIn('potato', page.entries)

            proxy = CookieProxy(client)
            clipboard = self.clipboard_module.Clipboard.from_request(proxy)
            clipboard.mode = 'copy'
            clipboard.add('potato')
            clipboard.to_response(proxy, proxy)

            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertIn('potato', page.entries)

            clipboard.mode = 'cut'
            clipboard.to_response(proxy, proxy)

            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertNotIn('potato', page.entries)


class TestAction(unittest.TestCase):
    module = file_actions
    clipboard_module = file_actions_clipboard

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

        @self.app.errorhandler(browsepy_exceptions.InvalidPathError)
        def handler(e):
            return '', 400

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

            response = client.post(
                '/file-actions/create/directory/..',
                data={
                    'name': 'asdf',
                    })
            self.assertEqual(response.status_code, 404)

            response = client.post(
                '/file-actions/create/directory/nowhere',
                data={
                    'name': 'asdf',
                    })
            self.assertEqual(response.status_code, 404)
            response = client.post(
                '/file-actions/create/directory',
                data={
                    'name': '..',
                    })
            self.assertEqual(response.status_code, 400)

    def test_selection(self):
        self.touch('a')
        self.touch('b')
        with self.app.test_client() as client:
            response = client.get('/file-actions/selection')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertEqual(page.urlpath, self.basename)
            self.assertIn('a', page.entries)
            self.assertIn('b', page.entries)

            response = client.get('/file-actions/selection/..')
            self.assertEqual(response.status_code, 404)

            response = client.get('/file-actions/selection/nowhere')
            self.assertEqual(response.status_code, 404)

    def test_paste(self):
        files = ['a', 'b', 'c']
        self.touch('a')
        self.touch('b')
        self.mkdir('c')
        self.mkdir('target')

        with self.app.test_client() as client:
            response = client.post(
                '/file-actions/selection',
                data={
                    'path': files,
                    'action-copy': 'whatever',
                    })
            self.assertEqual(response.status_code, 302)

            response = client.get('/file-actions/clipboard/paste/target')
            self.assertEqual(response.status_code, 302)

            for p in files:
                self.assertExist(p)

            for p in files:
                self.assertExist('target', p)

        with self.app.test_client() as client:
            response = client.post(
                '/file-actions/selection',
                data={
                    'path': files,
                    'action-cut': 'something',
                    })
            self.assertEqual(response.status_code, 302)

            response = client.get('/file-actions/clipboard/paste/target')
            self.assertEqual(response.status_code, 302)

            for p in files:
                self.assertNotExist(p)

            for p in files:
                self.assertExist('target', p)

        with self.app.test_client() as client:
            response = client.get('/file-actions/clipboard/paste/..')
            self.assertEqual(response.status_code, 404)
            response = client.get('/file-actions/clipboard/paste/nowhere')
            self.assertEqual(response.status_code, 404)

        with self.app.test_client() as client:
            proxy = CookieProxy(client)
            clipboard = self.clipboard_module.Clipboard.from_request(proxy)
            clipboard.mode = 'wrong-mode'
            clipboard.add('whatever')
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

            clipboard.mode = 'cut'
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 302)  # same location

            clipboard.mode = 'cut'
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste/target')
            self.assertEqual(response.status_code, 400)

            clipboard.mode = 'copy'
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

            clipboard.mode = 'copy'
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste/target')
            self.assertEqual(response.status_code, 400)

            self.app.config['exclude_fnc'] = lambda n: n.endswith('whatever')

            clipboard.mode = 'cut'
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

            clipboard.mode = 'copy'
            clipboard.to_response(proxy, proxy)

            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

    def test_clear(self):
        files = ['a', 'b']
        for p in files:
            self.touch(p)

        with self.app.test_client() as client:
            response = client.post(
                '/file-actions/selection',
                data={
                    'path': files,
                    })
            self.assertEqual(response.status_code, 302)

            response = client.get('/file-actions/clipboard/clear')
            self.assertEqual(response.status_code, 302)

            response = client.get('/file-actions/selection')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertFalse(page.selected)
