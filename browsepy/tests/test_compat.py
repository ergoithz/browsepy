import unittest
import re

from werkzeug.utils import cached_property

import browsepy.compat


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

    def test_fsdecode(self):
        path = b'/a/\xc3\xb1'
        self.assertEqual(
            self.module.fsdecode(path, os_name='posix', fs_encoding='utf-8'),
            path.decode('utf-8')
            )
        path = b'/a/\xf1'
        self.assertEqual(
            self.module.fsdecode(path, os_name='nt', fs_encoding='latin-1'),
            path.decode('latin-1')
            )
        path = b'/a/\xf1'
        self.assertRaises(
            UnicodeDecodeError,
            self.module.fsdecode,
            path,
            fs_encoding='utf-8',
            errors='strict'
        )

    def test_fsencode(self):
        path = b'/a/\xc3\xb1'
        self.assertEqual(
            self.module.fsencode(
                path.decode('utf-8'),
                fs_encoding='utf-8'
                ),
            path
            )
        path = b'/a/\xf1'
        self.assertEqual(
            self.module.fsencode(
                path.decode('latin-1'),
                fs_encoding='latin-1'
                ),
            path
            )
        path = b'/a/\xf1'
        self.assertEqual(
            self.module.fsencode(path, fs_encoding='utf-8'),
            path
            )

    def test_getcwd(self):
        self.assertIsInstance(self.module.getcwd(), self.module.unicode)
        self.assertIsInstance(
            self.module.getcwd(
                fs_encoding='latin-1',
                cwd_fnc=lambda: b'\xf1'
                ),
            self.module.unicode
            )
        self.assertIsInstance(
            self.module.getcwd(
                fs_encoding='utf-8',
                cwd_fnc=lambda: b'\xc3\xb1'
                ),
            self.module.unicode
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
