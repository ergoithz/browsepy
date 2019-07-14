# -*- coding: UTF-8 -*-

import os
import os.path
import unittest
import shutil
import tempfile

import six
import six.moves
import flask

from werkzeug.exceptions import NotFound

import browsepy
import browsepy.utils as utils
import browsepy.file as browsepy_file
import browsepy.manager as browsepy_manager
import browsepy.plugin.player as player
import browsepy.plugin.player.playable as player_playable


class ManagerMock(object):
    def __init__(self):
        self.blueprints = []
        self.mimetype_functions = []
        self.widgets = []
        self.arguments = []
        self.argument_values = {}

    def register_blueprint(self, blueprint):
        self.blueprints.append(blueprint)

    def register_mimetype_function(self, fnc):
        self.mimetype_functions.append(fnc)

    def register_widget(self, **kwargs):
        self.widgets.append(kwargs)

    def register_argument(self, *args, **kwargs):
        self.arguments.append((args, kwargs))

    def get_argument(self, name, default=None):
        return self.argument_values.get(name, default)


class TestPLSFileParser(unittest.TestCase):
    module = player_playable
    exceptions = player_playable.PLSFileParser.option_exceptions

    def get_parser(self, content=''):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(content)
            f.flush()
            return self.module.PLSFileParser(f.name)

    def test_getint(self):
        parser = self.get_parser()
        self.assertEqual(parser.getint('a', 'a', 2), 2)
        with self.assertRaises(self.exceptions):
            parser.getint('a', 'a')

    def test_get(self):
        parser = self.get_parser()
        self.assertEqual(parser.get('a', 'a', 2), 2)
        with self.assertRaises(self.exceptions):
            parser.get('a', 'a')


class TestPlayerBase(unittest.TestCase):
    module = player

    def assertPathEqual(self, a, b):
        return self.assertEqual(
            os.path.normcase(a),
            os.path.normcase(b)
            )

    def assertPathListEqual(self, a, b):
        return self.assertListEqual(
            list(map(os.path.normcase, a)),
            list(map(os.path.normcase, b))
            )

    def setUp(self):
        self.base = 'c:\\base' if os.name == 'nt' else '/base'
        self.app = flask.Flask(self.__class__.__name__)
        self.app.config.update(
            DIRECTORY_BASE=self.base,
            SERVER_NAME='localhost',
            )
        self.manager = ManagerMock()

    def tearDown(self):
        utils.clear_flask_context()


class TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        self.module.register_plugin(self.manager)
        self.assertListEqual(self.manager.arguments, [])

        self.assertIn(self.module.player, self.manager.blueprints)
        self.assertIn(
            self.module.playable.detect_playable_mimetype,
            self.manager.mimetype_functions
            )

        widgets = [
            action['filename']
            for action in self.manager.widgets
            if action['type'] == 'stylesheet'
            ]
        self.assertIn('css/browse.css', widgets)

        actions = [action['endpoint'] for action in self.manager.widgets]
        self.assertIn('player.static', actions)
        self.assertIn('player.audio', actions)
        self.assertIn('player.playlist', actions)
        self.assertNotIn('player.directory', actions)

    def test_register_plugin_with_arguments(self):
        self.manager.argument_values['player_directory_play'] = True
        self.module.register_plugin(self.manager)

        actions = [action['endpoint'] for action in self.manager.widgets]
        self.assertIn('player.directory', actions)

    def test_register_arguments(self):
        self.module.register_arguments(self.manager)
        self.assertEqual(len(self.manager.arguments), 1)

        arguments = [arg[0][0] for arg in self.manager.arguments]
        self.assertIn('--player-directory-play', arguments)


class TestIntegrationBase(TestPlayerBase):
    player_module = player
    browsepy_module = browsepy
    manager_module = browsepy_manager

    def tearDown(self):
        utils.clear_flask_context()


class TestIntegration(TestIntegrationBase):
    non_directory_args = ['--plugin', 'player']
    directory_args = ['--plugin', 'player', '--player-directory-play']

    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['PLUGIN_NAMESPACES'] = ('browsepy.plugin',)
        manager = self.manager_module.PluginManager(self.app)
        manager.load_plugin('player')
        self.assertIn(self.player_module.player, self.app.blueprints.values())

    def test_register_arguments(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['PLUGIN_NAMESPACES'] = ('browsepy.plugin',)

        manager = self.manager_module.ArgumentPluginManager(self.app)
        manager.load_arguments(self.non_directory_args)
        self.assertFalse(manager.get_argument('player_directory_play'))
        manager.load_arguments(self.directory_args)
        self.assertTrue(manager.get_argument('player_directory_play'))

    def test_reload(self):
        self.app.config.update(
            PLUGIN_MODULES=['player'],
            PLUGIN_NAMESPACES=['browsepy.plugin']
            )
        manager = self.manager_module.PluginManager(self.app)
        manager.load_arguments(self.non_directory_args)
        manager.reload()

        manager = self.manager_module.PluginManager(self.app)
        manager.load_arguments(self.directory_args)
        manager.reload()


class TestPlayable(TestIntegrationBase):
    module = player_playable

    def setUp(self):
        super(TestPlayable, self).setUp()
        self.manager = self.manager_module.PluginManager(
            self.app
            )
        self.manager.register_mimetype_function(
            self.player_module.playable.detect_playable_mimetype
            )

    def test_normalize_playable_path(self):
        playable = self.module.PlayListFile(
            path=p(self.base, 'a.m3u'),
            app=self.app
            )
        self.assertEqual(
            playable.normalize_playable_path('http://asdf/asdf.mp3'),
            'http://asdf/asdf.mp3'
            )
        self.assertEqual(
            playable.normalize_playable_path('ftp://asdf/asdf.mp3'),
            'ftp://asdf/asdf.mp3'
            )
        self.assertPathEqual(
            playable.normalize_playable_path('asdf.mp3'),
            self.base + '/asdf.mp3'
            )
        self.assertPathEqual(
            playable.normalize_playable_path(self.base + '/other/../asdf.mp3'),
            self.base + '/asdf.mp3'
            )
        self.assertEqual(
            playable.normalize_playable_path('/other/asdf.mp3'),
            None
            )

    def test_playablefile(self):
        exts = {
            'mp3': 'mp3',
            'wav': 'wav',
            'ogg': 'ogg'
            }
        for ext, media_format in exts.items():
            pf = self.module.PlayableFile(path='asdf.%s' % ext, app=self.app)
            self.assertEqual(pf.media_format, media_format)
            self.assertEqual(pf.title, 'asdf.%s' % ext)

    def test_playabledirectory(self):
        tmpdir = tempfile.mkdtemp()
        try:
            file = p(tmpdir, 'playable.mp3')
            open(file, 'w').close()
            node = browsepy_file.Directory(tmpdir, app=self.app)
            self.assertTrue(self.module.PlayableDirectory.detect(node))

            directory = self.module.PlayableDirectory(tmpdir, app=self.app)

            self.assertEqual(directory.parent.path, directory.path)

            entries = directory.entries()
            self.assertEqual(next(entries).path, file)
            self.assertRaises(StopIteration, next, entries)

            os.remove(file)
            self.assertFalse(self.module.PlayableDirectory.detect(node))

        finally:
            shutil.rmtree(tmpdir)

    def test_playlistfile(self):
        pf = self.module.PlayListFile.from_urlpath(
            path='filename.m3u', app=self.app)
        self.assertTrue(isinstance(pf, self.module.M3UFile))
        pf = self.module.PlayListFile.from_urlpath(
            path='filename.m3u8', app=self.app)
        self.assertTrue(isinstance(pf, self.module.M3UFile))
        pf = self.module.PlayListFile.from_urlpath(
            path='filename.pls', app=self.app)
        self.assertTrue(isinstance(pf, self.module.PLSFile))

    def test_m3ufile(self):
        data = '/base/valid.mp3\n/outside.ogg\n/base/invalid.bin\nrelative.ogg'
        tmpdir = tempfile.mkdtemp()
        try:
            file = p(tmpdir, 'playable.m3u')
            with open(file, 'w') as f:
                f.write(data)
            playlist = self.module.M3UFile(path=file, app=self.app)
            self.assertPathListEqual(
                [a.path for a in playlist.entries()],
                [p(self.base, 'valid.mp3'), p(tmpdir, 'relative.ogg')]
                )
        finally:
            shutil.rmtree(tmpdir)

    def test_plsfile(self):
        data = (
            '[playlist]\n'
            'File1=/base/valid.mp3\n'
            'File2=/outside.ogg\n'
            'File3=/base/invalid.bin\n'
            'File4=relative.ogg'
            )
        tmpdir = tempfile.mkdtemp()
        try:
            file = p(tmpdir, 'playable.pls')
            with open(file, 'w') as f:
                f.write(data)
            playlist = self.module.PLSFile(path=file, app=self.app)
            self.assertPathListEqual(
                [a.path for a in playlist.entries()],
                [p(self.base, 'valid.mp3'), p(tmpdir, 'relative.ogg')]
                )
        finally:
            shutil.rmtree(tmpdir)

    def test_plsfile_with_holes(self):
        data = (
            '[playlist]\n'
            'File1=/base/valid.mp3\n'
            'File3=/base/invalid.bin\n'
            'File4=relative.ogg\n'
            'NumberOfEntries=4'
            )
        tmpdir = tempfile.mkdtemp()
        try:
            file = p(tmpdir, 'playable.pls')
            with open(file, 'w') as f:
                f.write(data)
            playlist = self.module.PLSFile(path=file, app=self.app)
            self.assertPathListEqual(
                [a.path for a in playlist.entries()],
                [p(self.base, 'valid.mp3'), p(tmpdir, 'relative.ogg')]
                )
        finally:
            shutil.rmtree(tmpdir)


class TestBlueprint(TestPlayerBase):
    def setUp(self):
        super(TestBlueprint, self).setUp()
        app = self.app
        app.template_folder = utils.ppath('templates')
        app.config['DIRECTORY_BASE'] = tempfile.mkdtemp()
        app.register_blueprint(self.module.player)

        @app.route("/browse", defaults={"path": ""}, endpoint='browse')
        @app.route('/browse/<path:path>', endpoint='browse')
        @app.route('/open/<path:path>', endpoint='open')
        def dummy(path):
            pass

    def url_for(self, endpoint, **kwargs):
        with self.app.app_context():
            return flask.url_for(endpoint, **kwargs)

    def file(self, path, data=''):
        apath = p(self.app.config['DIRECTORY_BASE'], path)
        with open(apath, 'w') as f:
            f.write(data)
        return apath

    def directory(self, path):
        apath = p(self.app.config['DIRECTORY_BASE'], path)
        os.mkdir(apath)
        return apath

    def test_playable(self):
        name = 'test.mp3'
        url = self.url_for('player.audio', path=name)
        with self.app.test_client() as client:
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.file(name)
            result = client.get(url)
            self.assertEqual(result.status_code, 200)

    def test_playlist(self):
        name = 'test.m3u'
        url = self.url_for('player.playlist', path=name)
        with self.app.test_client() as client:
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.file(name)
            result = client.get(url)
            self.assertEqual(result.status_code, 200)

    def test_directory(self):
        name = 'directory'
        url = self.url_for('player.directory', path=name)
        with self.app.test_client() as client:
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.directory(name)
            result = client.get(url)
            self.assertEqual(result.status_code, 200)

            self.file('directory/test.mp3')
            result = client.get(url)
            self.assertEqual(result.status_code, 200)
            self.assertIn(b'test.mp3', result.data)

    def test_endpoints(self):
        with self.app.app_context():
            self.assertIsInstance(
                self.module.audio(path='..'),
                NotFound
                )

            self.assertIsInstance(
                self.module.playlist(path='..'),
                NotFound
                )

            self.assertIsInstance(
                self.module.directory(path='..'),
                NotFound
                )


def p(*args):
    args = [
        arg if isinstance(arg, six.text_type) else arg.decode('utf-8')
        for arg in args
        ]
    return os.path.join(*args)
