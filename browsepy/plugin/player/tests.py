import unittest
import browsepy

import browsepy.plugin.player as player
import browsepy.plugin.player.playable as player_playable

class TestPlayerBase(unittest.TestCase):
    module = player
    app = browsepy.app

    @classmethod
    def setUpClass(cls):
        player_module = TestPlayerBase.module
        if not player_module.player.name in cls.app.blueprints:
            player_module.register_plugin(cls.app.extensions['plugin_manager'])


def TestPlayer(TestPlayerBase):
    def test_register_plugin(self):
        self.assertIn(self.module.player.name, self.app.blueprints)


class TestPlayable(TestPlayerBase):
    module = player_playable

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
