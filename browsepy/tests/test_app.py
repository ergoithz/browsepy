import os
import os.path
import unittest
import warnings

import browsepy
import browsepy.compat as compat
import browsepy.appconfig


class TestApp(unittest.TestCase):
    module = browsepy
    app = browsepy.app

    def setUp(self):
        self.app.config._warned.clear()

    def test_config(self):
        with compat.mkdtemp() as path:
            name = os.path.join(path, 'file.py')
            with open(name, 'w') as f:
                f.write('DIRECTORY_DOWNLOADABLE = False\n')

            os.environ['BROWSEPY_TEST_SETTINGS'] = name
            with warnings.catch_warnings(record=True) as warns:
                warnings.simplefilter('always')
                self.app.config['directory_downloadable'] = True
                self.assertTrue(warns)

            self.app.config.from_envvar('BROWSEPY_TEST_SETTINGS')
            with warnings.catch_warnings(record=True) as warns:
                warnings.simplefilter('always')
                self.assertFalse(self.app.config['directory_downloadable'])
                self.assertFalse(warns)


class TestConfig(unittest.TestCase):
    pwd = os.path.dirname(os.path.abspath(__file__))
    module = browsepy.appconfig

    def test_case_insensitivity(self):
        cfg = self.module.Config(self.pwd, defaults={'prop': 2})
        self.assertEqual(cfg['prop'], cfg['PROP'])
        self.assertEqual(cfg['pRoP'], cfg.pop('prop'))
        cfg.update(prop=1)
        self.assertEqual(cfg['PROP'], 1)
        self.assertEqual(cfg.get('pRop'), 1)
        self.assertEqual(cfg.popitem(), ('PROP', 1))
        self.assertRaises(KeyError, cfg.pop, 'prop')
        cfg.update(prop=1)
        del cfg['PrOp']
        self.assertRaises(KeyError, cfg.__delitem__, 'prop')
        self.assertIsNone(cfg.pop('prop', None))
        self.assertIsNone(cfg.get('prop'))
