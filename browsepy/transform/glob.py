
import os
import warnings

from unicategories import categories as unicat, RangeGroup as ranges

from ..compat import re_escape, chr
from . import StateMachine


class GlobTransform(StateMachine):
    jumps = {
        'start': {
            '': 'text',  # edit on __init__
            },
        'text': {
            '*': 'wildcard',
            '**': 'wildcard',
            '?': 'wildcard',
            '[': 'range',
            '[!': 'range',
            '[]': 'range',
            '{': 'group',
            '\\': 'literal',
            },
        'literal': {
            c: 'text' for c in '\\*?[{'
            },
        'wildcard': {
            '': 'text',
            },
        'range': {
            ']': 'range_close',
            '[.': 'posix_collating_symbol',
            '[:': 'posix_character_class',
            '[=': 'posix_equivalence_class',
            },
        'range_ignore': {
            '': 'range',
            },
        'range_close': {
            '': 'text',
            },
        'posix_collating_symbol': {
            '.]': 'range_ignore',
            },
        'posix_character_class': {
            ':]': 'range_ignore',
            },
        'posix_equivalence_class': {
            '=]': 'range_ignore',
            },
        'group': {
            '}': 'group_close',
            },
        'group_close': {
            '': 'text',
            }
        }
    character_classes = {
        'alnum': (
            # [\p{L}\p{Nl}\p{Nd}]
            unicat['L'] + unicat['Nl'] + unicat['Nd']
            ),
        'alpha': (
            # \p{L}\p{Nl}
            unicat['L'] + unicat['Nl']
            ),
        'ascii': (
            # [\x00-\x7F]
            ranges(((0, 0x7F),))
            ),
        'blank': (
            # [\p{Zs}\t]
            unicat['Zs'] + ranges(((9, 10),))
            ),
        'cntrl': (
            # \p{Cc}
            unicat['Cc']
            ),
        'digit': (
            # \p{Nd}
            unicat['Nd']
            ),
        'graph': (
            # [^\p{Z}\p{C}]
            unicat['M'] + unicat['L'] + unicat['N'] + unicat['P'] + unicat['S']
            ),
        'lower': (
            # \p{Ll}
            unicat['Ll']
            ),
        'print': (
            # \P{C}
            unicat['C']
            ),
        'punct': (
            # \p{P}
            unicat['P']
            ),
        'space': (
            # [\p{Z}\t\r\n\v\f]
            unicat['Z'] + ranges(((9, 14),))
            ),
        'upper': (
            # \p{Lu}
            unicat['Lu']
            ),
        'word': (
            # [\p{L}\p{Nl}\p{Nd}\p{Pc}]
            unicat['L'] + unicat['Nl'] + unicat['Nd'] + unicat['Pc']
            ),
        'xdigit': (
            # [0-9A-Fa-f]
            ranges(((48, 58), (65, 71), (97, 103)))
            ),
        }
    current = 'start'
    deferred = False

    def __init__(self, data, sep=os.sep):
        self.sep = sep
        self.deferred_data = []
        self.jumps = dict(self.jumps)
        self.jumps['start'] = dict(self.jumps['start'])
        self.jumps['start'][sep] = 'text'
        super(GlobTransform, self).__init__(data)

    def flush(self):
        return '%s$' % super(GlobTransform, self).flush()

    def transform(self, data, mark, next):
        data = super(GlobTransform, self).transform(data, mark, next)
        if self.deferred:
            self.deferred_data.append(data)
            data = ''
        elif self.deferred_data:
            data = ''.join(self.deferred_data) + data
            self.deferred_data[:] = ()
        return data

    def transform_posix_collating_symbol(self, data, mark, next):
        warnings.warn(
            'Posix collating symbols (like %s%s) are not supported.'
            % (data, mark))
        return None

    def transform_posix_character_class(self, data, mark, next):
        name = data[len(self.start):]
        if name not in self.character_classes:
            warnings.warn(
                'Posix character class %s is not supported.'
                % name)
            return None
        return ''.join(
            chr(start)
            if 1 == end - start else
            '%s-%s' % (chr(start), chr(end - 1))
            for start, end in self.character_classes[name]
            )

    def transform_posix_equivalence_class(self, data, mark, next):
        warnings.warn(
            'Posix equivalence class expresions (like %s%s) are not supported.'
            % (data, mark))
        return None

    def transform_start(self, data, mark, next):
        if mark == self.sep:
            return '^'
        return self.transform_text(self.sep, mark, next)

    def transform_wildcard(self, data, mark, next):
        if self.start == '**':
            return '.*'
        if self.start == '*':
            return '[^%s]*' % self.sep
        return '.'

    def transform_text(self, data, mark, next):
        return re_escape(data)

    def transform_literal(self, data, mark, next):
        return data[len(self.start):]

    def transform_range(self, data, mark, next):
        self.deferred = True
        if self.start == '[!':
            return '[^%s' % data[2:]
        if self.start == '[]':
            return '[\\]%s' % data[2:]
        return data

    def transform_range_close(self, data, mark, next):
        self.deferred = False
        if None in self.deferred_data:
            self.deferred_data[:] = ()
            return '.'
        return data

    def transform_range_ignore(self, data, mark, next):
        return ''

    def transform_group(self, data, mark, next):
        return '(%s' % ('|'.join(data[len(self.start):].split(',')))

    def transform_group_close(self, data, mark, next):
        return ')'


def translate(data, sep=os.sep):
    self = GlobTransform(data)
    return ''.join(self)
