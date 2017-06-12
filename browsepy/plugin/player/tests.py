
import os
import os.path
import unittest
import shutil
import tempfile

import flask

from werkzeug.exceptions import NotFound

import browsepy
import browsepy.compat as compat
import browsepy.file as browsepy_file
import browsepy.manager as browsepy_manager
import browsepy.plugin.player as player
import browsepy.plugin.player.playable as player_playable
import browsepy.tests.utils as test_utils


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
        self.app.config['directory_base'] = self.base
        self.manager = ManagerMock()


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


class TestIntegration(TestIntegrationBase):
    non_directory_args = ['--plugin', 'player']
    directory_args = ['--plugin', 'player', '--player-directory-play']

    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['plugin_namespaces'] = ('browsepy.plugin',)
        manager = self.manager_module.PluginManager(self.app)
        manager.load_plugin('player')
        self.assertIn(self.player_module.player, self.app.blueprints.values())

    def test_register_arguments(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['plugin_namespaces'] = ('browsepy.plugin',)

        manager = self.manager_module.ArgumentPluginManager(self.app)
        manager.load_arguments(self.non_directory_args)
        self.assertFalse(manager.get_argument('player_directory_play'))
        manager.load_arguments(self.directory_args)
        self.assertTrue(manager.get_argument('player_directory_play'))

    def test_reload(self):
        self.app.config.update(
            plugin_modules=['player'],
            plugin_namespaces=['browsepy.plugin']
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
        self.manager = self.manager_module.MimetypePluginManager(
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

    def test_playabledirectory(self):
        tmpdir = tempfile.mkdtemp()
        try:
            file = p(tmpdir, 'playable.mp3')
            open(file, 'w').close()
            node = browsepy_file.Directory(tmpdir)
            self.assertTrue(self.module.PlayableDirectory.detect(node))

            directory = self.module.PlayableDirectory(tmpdir, app=self.app)
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
        self.app = browsepy.app  # required for our url_for calls
        self.app.config.update(
            directory_base=tempfile.mkdtemp(),
            SERVER_NAME='test'
        )
        self.app.register_blueprint(self.module.player)

    def tearDown(self):
        shutil.rmtree(self.app.config['directory_base'])
        test_utils.clear_flask_context()

    def url_for(self, endpoint, **kwargs):
        with self.app.app_context():
            return flask.url_for(endpoint, _external=False, **kwargs)

    def get(self, endpoint, **kwargs):
        with self.app.test_client() as client:
            url = self.url_for(endpoint, **kwargs)
            response = client.get(url)
        return response

    def file(self, path, data=''):
        apath = p(self.app.config['directory_base'], path)
        with open(apath, 'w') as f:
            f.write(data)
        return apath

    def directory(self, path):
        apath = p(self.app.config['directory_base'], path)
        os.mkdir(apath)
        return apath

    def test_playable(self):
        name = 'test.mp3'
        result = self.get('player.audio', path=name)
        self.assertEqual(result.status_code, 404)
        self.file(name)
        result = self.get('player.audio', path=name)
        self.assertEqual(result.status_code, 200)

    def test_playlist(self):
        name = 'test.m3u'
        result = self.get('player.playlist', path=name)
        self.assertEqual(result.status_code, 404)
        self.file(name)
        result = self.get('player.playlist', path=name)
        self.assertEqual(result.status_code, 200)

    def test_directory(self):
        name = 'directory'
        result = self.get('player.directory', path=name)
        self.assertEqual(result.status_code, 404)
        self.directory(name)
        result = self.get('player.directory', path=name)
        self.assertEqual(result.status_code, 200)
        self.file('directory/test.mp3')
        result = self.get('player.directory', path=name)
        self.assertEqual(result.status_code, 200)

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
        arg if isinstance(arg, compat.unicode) else arg.decode('utf-8')
        for arg in args
        ]
    return os.path.join(*args)
