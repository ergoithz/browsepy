import re
import os.path
import unittest
import functools

import pycodestyle


class DeferredReport(pycodestyle.StandardReport):
    def __init__(self, *args, **kwargs):
        self.print_fnc = kwargs.pop('print_fnc')
        self.location_base = kwargs.pop('location_base')
        super(DeferredReport, self).__init__(*args, **kwargs)

    @property
    def location(self):
        if self.filename:
            return os.path.relpath(self.filename, self.location_base)
        return self.filename

    def get_file_results(self):
        self._deferred_print.sort()
        for line_number, offset, code, text, doc in self._deferred_print:
            error = {
                'path': self.location,
                'row': self.line_offset + line_number,
                'col': offset + 1,
                'code': code,
                'text': text,
                }
            lines = [self._fmt % error]
            if line_number <= len(self.lines):
                line = self.lines[line_number - 1]
                lines.extend((
                    line.rstrip(),
                    re.sub(r'\S', ' ', line[:offset]) + '^'
                    ))
            if doc:
                lines.append('    ' + doc.strip())
            error['message'] = '\n'.join(lines)
            self.print_fnc(error)
        return self.file_errors


class TestCodeQuality(unittest.TestCase):
    base = os.path.join(
        os.path.dirname(__file__),
        os.path.pardir,
        )
    setup_py = os.path.join(base, '..', 'setup.py')
    config_file = os.path.join(base, '..', 'setup.cfg')

    def test_conformance(self):
        '''
        Test pep-8 conformance
        '''
        messages = []
        style = pycodestyle.StyleGuide(
            config_file=self.config_file,
            paths=[self.base, self.setup_py],
            reporter=functools.partial(
                DeferredReport,
                location_base=self.base,
                print_fnc=messages.append
                )
            )
        result = style.check_files()
        text = ''.join(
            '%s\n    %s' % ('' if n else '\n', line)
            for message in messages
            for n, line in enumerate(message['message'].splitlines())
            )
        self.assertEqual(
            result.total_errors, 0, "Code style errors:%s" % text)
