# -*- coding: UTF-8 -*-

import os
import os.path
import unittest
import tempfile

import six
import six.moves
import flask

import browsepy
import browsepy.compat as compat
import browsepy.utils as utils
import browsepy.file as browsepy_file
import browsepy.plugin.player as player
import browsepy.plugin.player.playable as player_playable
import browsepy.plugin.player.playlist as player_playlist


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
        self.base = tempfile.mkdtemp()
        self.app = browsepy.create_app()
        self.app.config.update(
            PLUGIN_NAMESPACES=['browsepy.plugin'],
            DIRECTORY_BASE=self.base,
            SERVER_NAME='localhost',
            )
        self.manager = self.app.extensions['plugin_manager']

    def tearDown(self):
        compat.rmtree(self.base)
        utils.clear_flask_context()


class TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        manager = ManagerMock()
        self.module.register_plugin(manager)
        self.assertListEqual(manager.arguments, [])

        self.assertIn(self.module.player, manager.blueprints)
        self.assertIn(
            self.module.playable.PlayableFile.detect_mimetype,
            manager.mimetype_functions
            )

        widgets = [
            action['filename']
            for action in manager.widgets
            if action['type'] == 'stylesheet'
            ]
        self.assertIn('css/browse.css', widgets)

        actions = [action['endpoint'] for action in manager.widgets]
        self.assertIn('player.static', actions)
        self.assertIn('player.play', actions)

    def test_register_plugin_with_arguments(self):
        manager = ManagerMock()
        manager.argument_values['player_directory_play'] = True
        self.module.register_plugin(manager)

        actions = [action['endpoint'] for action in manager.widgets]
        self.assertIn('player.play', actions)

    def test_register_arguments(self):
        manager = ManagerMock()
        self.module.register_arguments(manager)
        self.assertEqual(len(manager.arguments), 1)

        arguments = [arg[0][0] for arg in manager.arguments]
        self.assertIn('--player-directory-play', arguments)


class TestIntegrationBase(TestPlayerBase):
    player_module = player
    browsepy_module = browsepy


class TestIntegration(TestIntegrationBase):
    non_directory_args = ['--plugin', 'player']
    directory_args = ['--plugin', 'player', '--player-directory-play']

    def test_register_plugin(self):
        self.manager.load_plugin('player')
        self.assertIn(self.player_module.player, self.app.blueprints.values())

    def test_register_arguments(self):
        self.manager.load_arguments(self.non_directory_args)
        self.assertFalse(self.manager.get_argument('player_directory_play'))
        self.manager.load_arguments(self.directory_args)
        self.assertTrue(self.manager.get_argument('player_directory_play'))

    def test_reload(self):
        self.app.config.update(PLUGIN_MODULES=['player'])

        self.manager.load_arguments(self.non_directory_args)
        self.manager.reload()

        self.manager.load_arguments(self.directory_args)
        self.manager.reload()


class TestPlayable(TestIntegrationBase):
    module = player_playable

    def test_normalize_playable_path(self):
        playable = self.module.PlayableFile(
            path=p(self.base, 'a.m3u'),
            app=self.app
            )
        normalize = player_playlist.normalize_playable_path
        self.assertEqual(
            normalize('http://asdf/asdf.mp3', playable),
            'http://asdf/asdf.mp3'
            )
        self.assertEqual(
            normalize('ftp://asdf/asdf.mp3', playable),
            'ftp://asdf/asdf.mp3'
            )
        self.assertPathEqual(
            normalize('asdf.mp3', playable),
            self.base + '/asdf.mp3'
            )
        self.assertPathEqual(
            normalize(self.base + '/other/../asdf.mp3', playable),
            self.base + '/asdf.mp3'
            )
        self.assertEqual(
            normalize('/other/asdf.mp3', playable),
            None
            )

    def test_playablefile(self):
        exts = {
            'mp3': 'mp3',
            'wav': 'wav',
            'ogg': 'ogg'
            }
        for ext, extension in exts.items():
            pf = self.module.PlayableFile(path='asdf.%s' % ext, app=self.app)
            self.assertEqual(pf.extension, extension)
            self.assertEqual(pf.title, 'asdf.%s' % ext)

    def test_playabledirectory(self):
        file = p(self.base, 'playable.mp3')
        open(file, 'w').close()
        node = browsepy_file.Directory(self.base, app=self.app)
        self.assertTrue(self.module.PlayableDirectory.detect(node))

        directory = self.module.PlayableDirectory(self.base, app=self.app)

        self.assertEqual(directory.parent.path, directory.path)

        entries = directory.entries()
        self.assertEqual(next(entries).path, file)
        self.assertRaises(StopIteration, next, entries)

        os.remove(file)
        self.assertFalse(self.module.PlayableDirectory.detect(node))

    def test_playlistfile(self):
        pf = self.module.PlayableNode.from_urlpath(
            path='filename.m3u', app=self.app)
        self.assertTrue(isinstance(pf, self.module.PlayableFile))
        pf = self.module.PlayableNode.from_urlpath(
            path='filename.m3u8', app=self.app)
        self.assertTrue(isinstance(pf, self.module.PlayableFile))
        pf = self.module.PlayableNode.from_urlpath(
            path='filename.pls', app=self.app)
        self.assertTrue(isinstance(pf, self.module.PlayableFile))

    def test_m3ufile(self):
        data = (
            '{0}/valid.mp3\n'
            '/outside.ogg\n'
            '{0}/invalid.bin\n'
            'relative.ogg'
            ).format(self.base)
        file = p(self.base, 'playable.m3u')
        with open(file, 'w') as f:
            f.write(data)
        playlist = self.module.PlayableFile(path=file, app=self.app)
        self.assertPathListEqual(
            [a.path for a in playlist.entries()],
            [p(self.base, 'valid.mp3'), p(self.base, 'relative.ogg')]
            )

    def test_plsfile(self):
        data = (
            '[playlist]\n'
            'File1={0}/valid.mp3\n'
            'File2=/outside.ogg\n'
            'File3={0}/invalid.bin\n'
            'File4=relative.ogg'
            ).format(self.base)
        file = p(self.base, 'playable.pls')
        with open(file, 'w') as f:
            f.write(data)
        playlist = self.module.PlayableFile(path=file, app=self.app)
        self.assertPathListEqual(
            [a.path for a in playlist.entries()],
            [p(self.base, 'valid.mp3'), p(self.base, 'relative.ogg')]
            )

    def test_plsfile_with_holes(self):
        data = (
            '[playlist]\n'
            'File1={0}/valid.mp3\n'
            'File3={0}/invalid.bin\n'
            'File4=relative.ogg\n'
            'NumberOfEntries=4'
            ).format(self.base)
        file = p(self.base, 'playable.pls')
        with open(file, 'w') as f:
            f.write(data)
        playlist = self.module.PlayableFile(path=file, app=self.app)
        self.assertPathListEqual(
            [a.path for a in playlist.entries()],
            [p(self.base, 'valid.mp3'), p(self.base, 'relative.ogg')]
            )


class TestBlueprint(TestPlayerBase):
    def setUp(self):
        super(TestBlueprint, self).setUp()
        self.app.register_blueprint(self.module.player)

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
        url = self.url_for('player.play', path=name)
        with self.app.test_client() as client:
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.file(name)
            result = client.get(url)
            self.assertEqual(result.status_code, 200)

    def test_playlist(self):
        name = 'test.m3u'
        url = self.url_for('player.play', path=name)
        with self.app.test_client() as client:
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.file(name)
            result = client.get(url)
            self.assertEqual(result.status_code, 200)

    def test_directory(self):
        name = 'directory'
        url = self.url_for('player.play', path=name)
        with self.app.test_client() as client:
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.directory(name)
            result = client.get(url)
            self.assertEqual(result.status_code, 404)

            self.file('directory/test.mp3')
            result = client.get(url)
            self.assertEqual(result.status_code, 200)
            self.assertIn(b'test.mp3', result.data)


def p(*args):
    args = [
        arg if isinstance(arg, six.text_type) else arg.decode('utf-8')
        for arg in args
        ]
    return os.path.join(*args)
