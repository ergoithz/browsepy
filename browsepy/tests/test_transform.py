
import unittest
import warnings

import browsepy.transform.glob


class TestGlob(unittest.TestCase):
    module = browsepy.transform.glob
    translate = staticmethod(module.translate)

    def assertSubclass(self, cls, base):
        self.assertIn(base, cls.mro())

    def test_glob(self):
        translations = [
            ('/a', r'^/a$'),
            ('a', r'/a$'),
            ('/a*', r'^/a[^/]*$'),
            ('/a**', r'^/a.*$'),
            ('a?', r'/a.$'),
            ('/a{b,c}', r'^/a(b|c)$'),
            ('/a[a,b]', r'^/a[a,b]$'),
            ('/a[!b]', r'^/a[^b]$'),
            ('/a[]]', r'^/a[\]]$'),
            ('/a\\*', r'^/a\*$'),
            ('/[[:alpha:][:num:]]', '^/[[:alpha:][:num:]]$'),
            ('/[[:alpha:]0-5]', '^/[[:alpha:]0-5]$')
            ]
        self.assertListEqual(
            [self.translate(g) for g, r in translations],
            [r for g, r in translations]
            )

    def test_unsupported(self):
        translations = [
            ('[[.a-acute.]]a', '/.a$'),
            ('/[[=a=]]a', '^/.a$'),
            ('/[[=a=]\d]a', '^/.a$'),
            ]
        for source, result in translations:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                self.assertEqual(self.translate(source), result)
                self.assertSubclass(w[-1].category, Warning)
