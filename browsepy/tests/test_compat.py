
import unittest
import re

import browsepy.compat

from browsepy.compat import cached_property


class TestCompat(unittest.TestCase):
    module = browsepy.compat

    def _warn(self, message, category=None, stacklevel=None):
        if not hasattr(self, '_warnings'):
            self._warnings = []
        self._warnings.append({
            'message': message,
            'category': category,
            'stacklevel': stacklevel
            })

    @cached_property
    def assertWarnsRegex(self):
        supa = super(TestCompat, self)
        if hasattr(supa, 'assertWarnsRegex'):
            return supa.assertWarnsRegex
        return self.customAssertWarnsRegex

    def customAssertWarnsRegex(self, expected_warning, expected_regex, fnc,
                               *args, **kwargs):

        import warnings
        old_warn = warnings.warn
        warnings.warn = self._warn
        try:
            fnc(*args, **kwargs)
        finally:
            warnings.warn = old_warn
        warnings = ()
        if hasattr(self, '_warnings'):
            warnings = self._warnings
            del self._warnings
        regex = re.compile(expected_regex)
        self.assertTrue(any(
            warn['category'] == expected_warning and
            regex.match(warn['message'])
            for warn in warnings
            ))

    def test_which(self):
        self.assertTrue(self.module.which('python'))
        self.assertIsNone(self.module.which('lets-put-a-wrong-executable'))

    def test_pathconf(self):
        kwargs = {
            'os_name': 'posix',
            'pathconf_fnc': lambda x, k: 500,
            'pathconf_names': ('PC_PATH_MAX', 'PC_NAME_MAX')
            }
        pcfg = self.module.pathconf('/', **kwargs)
        self.assertEqual(pcfg['PC_PATH_MAX'], 500)
        self.assertEqual(pcfg['PC_NAME_MAX'], 500)
        kwargs.update(
            pathconf_fnc=None,
            )
        pcfg = self.module.pathconf('/', **kwargs)
        self.assertEqual(pcfg['PC_PATH_MAX'], 255)
        self.assertEqual(pcfg['PC_NAME_MAX'], 254)
        kwargs.update(
            os_name='nt',
            isdir_fnc=lambda x: False
            )
        pcfg = self.module.pathconf('c:\\a', **kwargs)
        self.assertEqual(pcfg['PC_PATH_MAX'], 259)
        self.assertEqual(pcfg['PC_NAME_MAX'], 255)
        kwargs.update(
            isdir_fnc=lambda x: True
            )
        pcfg = self.module.pathconf('c:\\a', **kwargs)
        self.assertEqual(pcfg['PC_PATH_MAX'], 246)
        self.assertEqual(pcfg['PC_NAME_MAX'], 242)

    def test_path(self):
        parse = self.module.pathparse
        self.assertListEqual(
            list(parse('"/":/escaped\\:path:asdf/', sep=':', os_sep='/')),
            ['/', '/escaped:path', 'asdf']
            )

    def test_getdebug(self):
        enabled = ('TRUE', 'true', 'True', '1', 'yes', 'enabled')
        for case in enabled:
            self.assertTrue(self.module.getdebug({'DEBUG': case}))
        disabled = ('FALSE', 'false', 'False', '', '0', 'no', 'disabled')
        for case in disabled:
            self.assertFalse(self.module.getdebug({'DEBUG': case}))

    def test_deprecated(self):
        environ = {'DEBUG': 'true'}
        self.assertWarnsRegex(
            DeprecationWarning,
            'DEPRECATED',
            self.module.deprecated('DEPRECATED', environ)(lambda: None)
            )
