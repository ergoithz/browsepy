import unittest
import os
import os.path
import tempfile
import shutil
import browsepy.__main__


class TestMain(unittest.TestCase):
    module = browsepy.__main__

    def setUp(self):
        self.app = browsepy.app
        self.parser = self.module.ArgParse(sep=os.sep)
        self.base = tempfile.mkdtemp()
        self.exclude_file = os.path.join(self.base, '.ignore')
        with open(self.exclude_file, 'w') as f:
            f.write('.ignore\n')

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_defaults(self):
        result = self.parser.parse_args([])
        self.assertEqual(result.host, '127.0.0.1')
        self.assertEqual(result.port, 8080)
        self.assertEqual(result.directory, os.getcwd())
        self.assertEqual(result.initial, None)
        self.assertEqual(result.removable, None)
        self.assertEqual(result.upload, None)
        self.assertListEqual(result.exclude, [])
        self.assertListEqual(result.exclude_from, [])
        self.assertEqual(result.plugin, [])

    def test_params(self):
        plugins = ['plugin_1', 'plugin_2', 'namespace.plugin_3']
        result = self.parser.parse_args([
            '127.1.1.1',
            '5000',
            '--directory=%s' % self.base,
            '--initial=%s' % self.base,
            '--removable=%s' % self.base,
            '--upload=%s' % self.base,
            '--exclude=a',
            '--exclude-from=%s' % self.exclude_file,
            ] + [
            '--plugin=%s' % plugin
            for plugin in plugins
            ])
        self.assertEqual(result.host, '127.1.1.1')
        self.assertEqual(result.port, 5000)
        self.assertEqual(result.directory, self.base)
        self.assertEqual(result.initial, self.base)
        self.assertEqual(result.removable, self.base)
        self.assertEqual(result.upload, self.base)
        self.assertListEqual(result.exclude, ['a'])
        self.assertListEqual(result.exclude_from, [self.exclude_file])
        self.assertEqual(result.plugin, plugins)

        result = self.parser.parse_args([
            '--directory', self.base,
            '--plugin', ','.join(plugins),
            '--exclude', '/.*'
            ])
        self.assertEqual(result.directory, self.base)
        self.assertEqual(result.plugin, plugins)
        self.assertListEqual(result.exclude, ['/.*'])

        result = self.parser.parse_args([
            '--directory=%s' % self.base,
            '--initial='
            ])
        self.assertEqual(result.host, '127.0.0.1')
        self.assertEqual(result.port, 8080)
        self.assertEqual(result.directory, self.base)
        self.assertIsNone(result.initial)
        self.assertIsNone(result.removable)
        self.assertIsNone(result.upload)
        self.assertListEqual(result.exclude, [])
        self.assertListEqual(result.exclude_from, [])
        self.assertListEqual(result.plugin, [])

        self.assertRaises(
            SystemExit,
            self.parser.parse_args,
            ['--directory=%s' % __file__]
        )

        self.assertRaises(
            SystemExit,
            self.parser.parse_args,
            ['--exclude-from=non-existing']
        )

    def test_exclude(self):
        result = self.parser.parse_args([
            '--exclude', '/.*',
            '--exclude-from', self.exclude_file,
        ])
        extra = self.module.collect_exclude_patterns(result.exclude_from)
        self.assertListEqual(extra, ['.ignore'])
        match = self.module.create_exclude_fnc(
            result.exclude + extra, '/b', sep='/')
        self.assertTrue(match('/b/.a'))
        self.assertTrue(match('/b/.a/b'))
        self.assertFalse(match('/b/a/.a'))
        self.assertTrue(match('/b/a/.ignore'))

        match = self.module.create_exclude_fnc(
            result.exclude + extra, 'C:\\b', sep='\\')
        self.assertTrue(match('C:\\b\\.a'))
        self.assertTrue(match('C:\\b\\.a\\b'))
        self.assertFalse(match('C:\\b\\a\\.a'))
        self.assertTrue(match('C:\\b\\a\\.ignore'))

    def test_main(self):
        params = {}
        self.module.main(
            argv=[],
            run_fnc=lambda app, **kwargs: params.update(kwargs)
            )

        defaults = {
            'host': '127.0.0.1',
            'port': 8080,
            'debug': False,
            'threaded': True
            }
        params_subset = {k: v for k, v in params.items() if k in defaults}
        self.assertEqual(defaults, params_subset)

    def test_filter_union(self):
        fu = self.module.filter_union
        self.assertIsNone(fu())
        self.assertIsNone(fu(None))
        self.assertIsNone(fu(None, None))

        def fnc1(path):
            return False

        self.assertEqual(fu(fnc1), fnc1)

        def fnc2(path):
            return True

        self.assertTrue(fu(fnc1, fnc2)('a'))
