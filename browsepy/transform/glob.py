
import os
import warnings

import regex

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
            ':]': 'range',
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
        return regex.escape(data, special_only=True)

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
