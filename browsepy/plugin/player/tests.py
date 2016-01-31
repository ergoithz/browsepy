

import flask

import unittest

import browsepy
import browsepy.manager as browsepy_manager
import browsepy.plugin.player as player
import browsepy.plugin.player.playable as player_playable

class ManagerMock(object):
    def __init__(self):
        self.blueprints = []
        self.mimetype_functions = []
        self.actions = []
        self.widgets = []

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


class TestPlayerBase(unittest.TestCase):
    module = player

    def setUp(self):
        self.app = flask.Flask(self.__class__.__name__)
        self.manager = ManagerMock()


class TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        self.module.register_plugin(self.manager)

        self.assertIn(self.module.player, self.manager.blueprints)
        self.assertIn(self.module.detect_playable_mimetype, self.manager.mimetype_functions)

        widgets = [action[1] for action in self.manager.widgets]
        self.assertIn('player.static', widgets)

        widgets = [action[2] for action in self.manager.widgets]
        self.assertIn({'filename': 'css/browse.css'}, widgets)

        actions = [action[0] for action in self.manager.actions]
        self.assertIn('player.audio', actions)
        self.assertIn('player.playlist', actions)


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
        self.manager = self.manager_module.MimetypeActionPluginManager(self.app)
        self.manager.register_mimetype_function(self.player_module.detect_playable_mimetype)

    def test_playablefile(self):
        exts = {
         'mp3': 'mp3',
         'wav': 'wav',
         'ogg': 'ogg'
        }
        for ext, media_format in exts.items():
            pf = self.module.PlayableFile(path = 'asdf.%s' % ext, app=self.app)
            self.assertEqual(pf.media_format, media_format)

    def test_playlistfile(self):
        pf = self.module.PlayListFile(path='filename.m3u', app=self.app)
        self.assertTrue(isinstance(pf, self.module.M3UFile))
        pf = self.module.PlayListFile(path='filename.m3u8', app=self.app)
        self.assertTrue(isinstance(pf, self.module.M3UFile))
        pf = self.module.PlayListFile(path='filename.pls', app=self.app)
        self.assertTrue(isinstance(pf, self.module.PLSFile))

    def test_m3ufile(self):
        pass
