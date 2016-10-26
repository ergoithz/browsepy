
import os
import os.path
import unittest
import shutil

import flask
import tempfile

import browsepy
import browsepy.file as browsepy_file
import browsepy.manager as browsepy_manager
import browsepy.plugin.player as player
import browsepy.plugin.player.playable as player_playable


class ManagerMock(object):
    def __init__(self):
        self.blueprints = []
        self.mimetype_functions = []
        self.actions = []
        self.widgets = []
        self.arguments = []
        self.argument_values = {}

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

    def register_argument(self, *args, **kwargs):
        self.arguments.append((args, kwargs))

    def get_argument(self, name, default=None):
        return self.argument_values.get(name, default)


class TestPlayerBase(unittest.TestCase):
    module = player

    def setUp(self):
        self.app = flask.Flask(self.__class__.__name__)
        self.app.config['directory_base'] = '/base'
        self.manager = ManagerMock()


class TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        self.module.register_plugin(self.manager)
        self.assertListEqual(self.manager.arguments, [])

        self.assertIn(self.module.player, self.manager.blueprints)
        self.assertIn(
            self.module.detect_playable_mimetype,
            self.manager.mimetype_functions
            )

        widgets = [action[1] for action in self.manager.widgets]
        self.assertIn('player.static', widgets)

        widgets = [action[2] for action in self.manager.widgets]
        self.assertIn({'filename': 'css/browse.css'}, widgets)

        actions = [action[0] for action in self.manager.actions]
        self.assertIn('player.audio', actions)
        self.assertIn('player.playlist', actions)
        self.assertNotIn('player.directory', actions)

    def test_register_plugin_with_arguments(self):
        self.manager.argument_values['player_directory_play'] = True
        self.module.register_plugin(self.manager)

        actions = [action[0] for action in self.manager.actions]
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
    def test_register_plugin(self):
        self.app.config.update(self.browsepy_module.app.config)
        self.app.config['plugin_namespaces'] = ('browsepy.plugin',)
        self.manager = self.manager_module.PluginManager(self.app)
        self.manager.load_plugin('player')
        self.assertIn(self.player_module.player, self.app.blueprints.values())


class TestPlayable(TestIntegrationBase):
    module = player_playable

    def setUp(self):
        super(TestIntegrationBase, self).setUp()
        self.manager = self.manager_module.MimetypeActionPluginManager(
            self.app
            )
        self.manager.register_mimetype_function(
            self.player_module.detect_playable_mimetype
            )

    def test_normalize_playable_path(self):
        playable = self.module.PlayListFile(path='/base/a.m3u', app=self.app)
        self.assertEqual(
            playable.normalize_playable_path('http://asdf/asdf.mp3'),
            'http://asdf/asdf.mp3'
            )
        self.assertEqual(
            playable.normalize_playable_path('ftp://asdf/asdf.mp3'),
            'ftp://asdf/asdf.mp3'
            )
        self.assertEqual(
            playable.normalize_playable_path('asdf.mp3'),
            '/base/asdf.mp3'
            )
        self.assertEqual(
            playable.normalize_playable_path('/base/other/../asdf.mp3'),
            '/base/asdf.mp3'
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
            file = os.path.join(tmpdir, 'playable.mp3')
            open(file, 'w').close()
            node = browsepy_file.Directory(tmpdir)
            self.assertTrue(self.module.PlayableDirectory.detect(node))
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
            file = os.path.join(tmpdir, 'playable.m3u')
            with open(file, 'w') as f:
                f.write(data)
            playlist = self.module.M3UFile(path=file, app=self.app)
            self.assertListEqual(
                [a.path for a in playlist.entries()],
                ['/base/valid.mp3', '%s/relative.ogg' % tmpdir]
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
            file = os.path.join(tmpdir, 'playable.pls')
            with open(file, 'w') as f:
                f.write(data)
            playlist = self.module.PLSFile(path=file, app=self.app)
            self.assertListEqual(
                [a.path for a in playlist.entries()],
                ['/base/valid.mp3', '%s/relative.ogg' % tmpdir]
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
            file = os.path.join(tmpdir, 'playable.pls')
            with open(file, 'w') as f:
                f.write(data)
            playlist = self.module.PLSFile(path=file, app=self.app)
            self.assertListEqual(
                [a.path for a in playlist.entries()],
                ['/base/valid.mp3', '%s/relative.ogg' % tmpdir]
                )
        finally:
            shutil.rmtree(tmpdir)
