import os
import os.path
import unittest
import tempfile

import browsepy
import browsepy.appconfig


class TestApp(unittest.TestCase):
    module = browsepy
    app = browsepy.app

    def test_config(self):
        try:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b'DIRECTORY_DOWNLOADABLE = False\n')
                name = f.name
            os.environ['BROWSEPY_TEST_SETTINGS'] = name
            self.app.config['directory_downloadable'] = True
            self.app.config.from_envvar('BROWSEPY_TEST_SETTINGS')
            self.assertFalse(self.app.config['directory_downloadable'])
        finally:
            os.remove(name)


class TestConfig(unittest.TestCase):
    pwd = os.path.dirname(os.path.abspath(__file__))
    module = browsepy.appconfig

    def test_case_insensitivity(self):
        cfg = self.module.Config(self.pwd, defaults={'prop': 1})
        self.assertEqual(cfg['prop'], cfg['PROP'])
        self.assertEqual(cfg['pRoP'], cfg.pop('prop'))
        cfg.update(prop=1)
        self.assertEqual(cfg['PROP'], 1)
        self.assertEqual(cfg.get('pRop'), 1)
        self.assertEqual(cfg.popitem(), ('PROP', 1))
        self.assertRaises(KeyError, cfg.pop, 'prop')
        self.assertIsNone(cfg.pop('prop', None))
        self.assertIsNone(cfg.get('prop'))
