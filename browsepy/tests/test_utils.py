# -*- coding: UTF-8 -*-

import sys
import io
import os
import os.path
import functools
import unittest
import tempfile

import browsepy.utils as utils


class TestPPath(unittest.TestCase):
    module = utils

    def test_bad_kwarg(self):
        with self.assertRaises(TypeError) as e:
            self.module.ppath('a', 'b', bad=1)
            self.assertIn('\'bad\'', e.args[0])

    def test_defaultsnamedtuple(self):
        dnt = self.module.defaultsnamedtuple

        tup = dnt('a', ('a', 'b', 'c'))
        self.assertListEqual(list(tup(1, 2, 3)), [1, 2, 3])

        tup = dnt('a', ('a', 'b', 'c'), {'b': 2})
        self.assertListEqual(list(tup(1, c=3)), [1, 2, 3])

        tup = dnt('a', ('a', 'b', 'c'), (1, 2, 3))
        self.assertListEqual(list(tup(c=10)), [1, 2, 10])

    def test_join(self):
        self.assertTrue(
            self.module
            .ppath('a', 'b', module=__name__)
            .endswith('browsepy/tests/a/b')
            )
        self.assertTrue(
            self.module
            .ppath('a', 'b')
            .endswith('browsepy/a/b')
            )

    def test_get_module(self):
        oldpath = sys.path[:]
        try:
            with tempfile.TemporaryDirectory() as base:
                ppath = functools.partial(os.path.join, base)
                sys.path[:] = [base]

                p = ppath('_test_zderr.py')
                with io.open(p, 'w', encoding='utf8') as f:
                    f.write('\na = 1 / 0\n')
                with self.assertRaises(ZeroDivisionError):
                    self.module.get_module('_test_zderr')

                p = ppath('_test_importerr.py')
                with io.open(p, 'w', encoding='utf8') as f:
                    f.write(
                        '\n'
                        'import os\n'
                        'import _this_module_should_not_exist_ as m\n'
                        'm.something()\n'
                        )
                with self.assertRaises(ImportError):
                    self.module.get_module('_test_importerr')

        finally:
            sys.path[:] = oldpath
