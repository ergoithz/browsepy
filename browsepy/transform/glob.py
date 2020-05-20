
import os
import warnings

from unicategories import categories as unicat, RangeGroup as ranges

from ..compat import re_escape, chr
from . import StateMachine


class GlobTransform(StateMachine):
    jumps = {
        'start': {
            '': 'text',
            '/': 'sep',
            },
        'text': {
            '*': 'wildcard',
            '**': 'wildcard',
            '?': 'wildcard',
            '[': 'range',
            '[!': 'range',
            '[]': 'range',
            '{': 'group',
            ',': 'group',
            '}': 'group',
            '\\': 'literal',
            '/': 'sep',
            },
        'sep': {
            '': 'text',
            },
        'literal': {
            c: 'text' for c in ('\\', '*', '?', '[', '{', '}', ',', '/', '')
            },
        'wildcard': {
            '': 'text',
            },
        'range': {
            '/': 'range_sep',
            ']': 'range_close',
            '[.': 'posix_collating_symbol',
            '[:': 'posix_character_class',
            '[=': 'posix_equivalence_class',
            },
        'range_sep': {
            '': 'range',
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
            '': 'text',
            },
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
            ranges(((0, 0x80),))
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
            # [\p{Z}\t\n\v\f\r]
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

    def __init__(self, data, sep=os.sep, base=None):
        self.sep = sep
        self.base = base or ''
        self.deferred_data = []
        self.deep = 0
        super(GlobTransform, self).__init__(data)

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

    def transform_wildcard(self, data, mark, next):
        if self.start == '**':
            return '.*'
        if self.start == '*':
            return '[^%s]*' % re_escape(self.sep)
        return '[^%s]' % re_escape(self.sep)

    def transform_text(self, data, mark, next):
        if next is None:
            return '%s(%s|$)' % (re_escape(data), re_escape(self.sep))
        return re_escape(data)

    def transform_sep(self, data, mark, next):
        return re_escape(self.sep)

    def transform_literal(self, data, mark, next):
        return data[len(self.start):]

    def transform_range(self, data, mark, next):
        self.deferred = True
        if self.start == '[!':
            return '[^%s' % data[2:]
        if self.start == '[]':
            return '[\\]%s' % data[2:]
        return data

    def transform_range_sep(self, data, mark, next):
        return re_escape(self.sep)

    def transform_range_close(self, data, mark, next):
        self.deferred = False
        if None in self.deferred_data:
            self.deferred_data[:] = ()
            return '.'
        return data

    def transform_range_ignore(self, data, mark, next):
        return ''

    def transform_group(self, data, mark, next):
        if self.start == '{':
            self.deep += 1
            return '('
        if self.start == ',' and self.deep:
            return '|'
        if self.start == '}' and self.deep:
            self.deep -= 1
            return ')'
        return data

    def transform_start(self, data, mark, next):
        if mark == '/':
            return '^%s' % re_escape(self.base)
        return re_escape(self.sep)


def translate(data, sep=os.sep, base=None):
    self = GlobTransform(data, sep, base)
    return ''.join(self)
