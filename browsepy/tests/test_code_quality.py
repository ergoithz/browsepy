import unittest

import six
import pycodestyle

from . import meta


class TestCodeFormat(six.with_metaclass(meta.TestFileMeta, unittest.TestCase)):
    """pycodestyle unit test"""

    meta_module = 'browsepy'
    meta_prefix = 'code'
    meta_file_extensions = ('.py',)

    def meta_test(self, module, filename):
        style = pycodestyle.StyleGuide(quiet=False)
        with self.path(module, filename) as f:
            result = style.check_files([str(f)])
        self.assertFalse(result.total_errors, (
            'Found {errors} code style error{s} (or warning{s}) '
            'on module {module}, file {filename!r}.').format(
                errors=result.total_errors,
                s='s' if result.total_errors > 1 else '',
                module=module,
                filename=filename,
                )
            )
