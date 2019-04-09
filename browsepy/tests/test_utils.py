# -*- coding: UTF-8 -*-

import unittest

import browsepy.utils as utils


class TestPPath(unittest.TestCase):
    def test_bad_kwarg(self):
        with self.assertRaises(TypeError) as e:
            utils.ppath('a', 'b', bad=1)
            self.assertIn('\'bad\'', e.args[0])

    def test_join(self):
        self.assertTrue(
            utils
            .ppath('a', 'b', module=__name__)
            .endswith('browsepy/tests/a/b')
            )
        self.assertTrue(
            utils
            .ppath('a', 'b')
            .endswith('browsepy/a/b')
            )
