
import unittest

import browsepy.transform.glob


class TestGlob(unittest.TestCase):
    module = browsepy.transform.glob
    translate = staticmethod(module.translate)

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
            ]
        self.assertListEqual(
            [self.translate(g) for g, r in translations],
            [r for g, r in translations]
            )
