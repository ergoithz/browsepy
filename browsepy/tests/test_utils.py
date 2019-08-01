# -*- coding: UTF-8 -*-

import sys
import os
import os.path
import functools
import unittest

import browsepy.utils as utils
import browsepy.compat as compat


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
            .endswith(os.path.join('browsepy', 'tests', 'a', 'b'))
            )
        self.assertTrue(
            self.module
            .ppath('a', 'b')
            .endswith(os.path.join('browsepy', 'a', 'b'))
            )

    def test_get_module(self):
        oldpath = sys.path[:]
        try:
            with compat.mkdtemp() as base:
                p = functools.partial(os.path.join, base)
                sys.path[:] = [base]

                with open(p('_test_zderr.py'), 'w') as f:
                    f.write('\na = 1 / 0\n')
                with self.assertRaises(ZeroDivisionError):
                    self.module.get_module('_test_zderr')

                with open(p('_test_importerr.py'), 'w') as f:
                    f.write(
                        '\n'
                        'import browsepy.tests.test_utils.failing\n'
                        'm.something()\n'
                        )
                with self.assertRaises(ImportError):
                    self.module.get_module('_test_importerr')

        finally:
            sys.path[:] = oldpath
