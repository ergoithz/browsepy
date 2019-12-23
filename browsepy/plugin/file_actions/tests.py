
import unittest
import tempfile
import os
import os.path
import functools

import bs4
import flask

import browsepy.compat as compat
import browsepy.utils as utils
import browsepy.plugin.file_actions as file_actions
import browsepy.plugin.file_actions.exceptions as file_actions_exceptions
import browsepy.file as browsepy_file
import browsepy.manager as browsepy_manager
import browsepy.exceptions as browsepy_exceptions
import browsepy

from browsepy.compat import cached_property


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
            DIRECTORY_BASE=self.base,
            EXCLUDE_FNC=None,
            )

    def tearDown(self):
        utils.clear_flask_context()

    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['PLUGIN_NAMESPACES'] = ('browsepy.plugin',)
        manager = self.manager_module.PluginManager(self.app)
        manager.load_plugin('file-actions')
        self.assertIn(
            self.actions_module.actions,
            self.app.blueprints.values()
            )

    def test_reload(self):
        self.app.config.update(
            PLUGIN_MODULES=[],
            PLUGIN_NAMESPACES=[]
            )
        manager = self.manager_module.PluginManager(self.app)
        self.assertNotIn(
            self.actions_module.actions,
            self.app.blueprints.values()
            )
        self.app.config.update(
            PLUGIN_MODULES=['file-actions'],
            PLUGIN_NAMESPACES=['browsepy.plugin']
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

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.app = self.browsepy_module.app
        self.original_config = dict(self.app.config)
        self.app.config.update(
            SECRET_KEY='secret',
            DIRECTORY_BASE=self.base,
            DIRECTORY_START=self.base,
            DIRECTORY_UPLOAD=None,
            EXCLUDE_FNC=None,
            PLUGIN_MODULES=['file-actions'],
            PLUGIN_NAMESPACES=[
                'browsepy.plugin'
                ]
            )
        self.manager = self.app.extensions['plugin_manager']
        self.manager.reload()

    def tearDown(self):
        compat.rmtree(self.base)
        self.app.config.clear()
        self.app.config.update(self.original_config)
        self.manager.clear()
        utils.clear_flask_context()

    def test_detection(self):
        url = functools.partial(flask.url_for, path='')

        with self.app.test_client() as client:
            self.app.config['DIRECTORY_UPLOAD'] = self.base
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

            with client.session_transaction() as session:
                session['clipboard:mode'] = 'copy'
                session['clipboard:items'] = ['whatever']

            self.app.config['DIRECTORY_UPLOAD'] = 'whatever'
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

            self.app.config['DIRECTORY_UPLOAD'] = self.base
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

            with client.session_transaction() as session:
                session['clipboard:mode'] = 'copy'
                session['clipboard:items'] = ['potato']
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertIn('potato', page.entries)

            with client.session_transaction() as session:
                session['clipboard:mode'] = 'cut'
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertNotIn('potato', page.entries)


class TestAction(unittest.TestCase):
    module = file_actions

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.basename = os.path.basename(self.base)
        self.app = flask.Flask('browsepy')
        self.app.register_blueprint(browsepy.blueprint)
        self.app.register_blueprint(self.module.actions)
        self.app.config.update(
            SECRET_KEY='secret',
            DIRECTORY_BASE=self.base,
            DIRECTORY_UPLOAD=self.base,
            DIRECTORY_REMOVE=self.base,
            EXCLUDE_FNC=None,
            USE_BINARY_MULTIPLES=True,
            )
        self.app.add_url_rule(
            '/browse/<path:path>',
            endpoint='browsepy.browse',
            view_func=lambda path: None
            )

        @self.app.errorhandler(browsepy_exceptions.InvalidPathError)
        def handler(e):
            return '', 400

    def tearDown(self):
        compat.rmtree(self.base)
        utils.clear_flask_context()

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
                '/file-actions/create/directory',
                data={
                    'name': 'asdf'
                    })
            self.assertEqual(response.status_code, 400)  # already exists

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

            response = client.post(
                '/file-actions/create/directory',
                data={
                    'name': '\0',
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

            response = client.post('/file-actions/selection', data={})
            self.assertEqual(response.status_code, 400)

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
            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'wrong-mode'
            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'cut'
            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 302)  # same location

            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'cut'
            response = client.get('/file-actions/clipboard/paste/target')
            self.assertEqual(response.status_code, 400)

            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'copy'
            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'copy'
            response = client.get('/file-actions/clipboard/paste/target')
            self.assertEqual(response.status_code, 400)

            self.app.config['EXCLUDE_FNC'] = lambda n: n.endswith('whatever')

            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'cut'
            response = client.get('/file-actions/clipboard/paste')
            self.assertEqual(response.status_code, 400)

            with client.session_transaction() as session:
                session['clipboard:items'] = ['whatever']
                session['clipboard:mode'] = 'copy'
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
                    'action-copy': 'whatever',
                    })
            self.assertEqual(response.status_code, 302)

            response = client.get('/file-actions/clipboard/clear')
            self.assertEqual(response.status_code, 302)

            response = client.get('/file-actions/selection')
            self.assertEqual(response.status_code, 200)
            page = Page(response.data)
            self.assertFalse(page.selected)


class TestException(unittest.TestCase):
    module = file_actions_exceptions
    node_class = browsepy_file.Node

    def setUp(self):
        self.app = flask.Flask('browsepy')

    def tearDown(self):
        utils.clear_flask_context()

    def test_invalid_clipboard_items_error(self):
        pair = (
            self.node_class('/base/asdf', app=self.app),
            Exception('Uncaught exception /base/asdf'),
            )
        e = self.module.InvalidClipboardItemsError(
            path='/',
            mode='cut',
            clipboard=('asdf,'),
            issues=[pair]
            )
        e.append(
            self.node_class('/base/other', app=self.app),
            OSError(2, 'Not found with random message'),
            )
        self.assertIn('Uncaught exception asdf', e.issues[0].message)
        self.assertIn('No such file or directory', e.issues[1].message)
