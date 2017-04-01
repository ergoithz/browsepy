
import os
import warnings

import regex

from browsepy.transform import StateMachine


class BlobTransform(StateMachine):
    jumps = {
        'start': {
            '': 'text',
            },
        'text': dict(**{
            '*': 'wildcard',
            '**': 'wildcard',
            '?': 'wildcard',
            '[': 'range',
            '[!': 'range',
            '[]': 'range',
            '{': 'group',
            }, **{
            '\\%s' % c: 'text_literal' for c in '\\*?[{'
            }),
        'text_literal': {
            '': 'text',
            },
        'ignore': {
            '': 'text',
            },
        'wildcard': {
            '': 'text',
            },
        'range': {
            ']': 'text_literal',
            '[.': 'posix_collating_symbol',
            '[:': 'posix_character_class',
            '[=': 'posix_equivalence_class',
            },
        'range_literal': {
            '': 'range',
            },
        'posix_collating_symbol': {
            '.]': 'ignore',
            },
        'posix_character_class': {
            ':]': 'range_literal',
            },
        'posix_equivalence_class': {
            '=]': 'ignore',
            },
        'group': {
            '}': 'group_close',
            },
        'group_close': {
            '': 'text',
            }
        }
    current = 'start'

    def __init__(self, data, sep=os.sep):
        self.sep = sep
        self.jumps['start'][sep] = self.jumps['start']['']
        super(BlobTransform, self).__init__(data)

    def flush(self):
        return '%s$' % super(BlobTransform, self).flush()

    def transform_posix_collating_class(self, data, mark, next):
        warnings.warn(
            'Posix collating symbols (like %s%s) are not supported.'
            % (data, mark))
        return '.'

    def transform_posix_equivalence_class(self, data, mark, next):
        warnings.warn(
            'Posix equivalence class expresions (like %s%s) are not supported.'
            % (data, mark))
        return '.'

    def transform_ignore(self, data, mark, next):
        return ''

    def transform_start(self, data, mark, next):
        if mark == self.sep:
            return '^'
        return regex.escape(self.sep, special_only=True)

    def transform_wildcard(self, data, mark, next):
        if self.start == '**':
            return '.*'
        if self.start == '*':
            return '[^%s]*' % self.sep
        return '.'

    def transform_text(self, data, mark, next):
        return regex.escape(data, special_only=True)

    def transform_range(self, data, mark, next):
        if self.start == '[!':
            return '[^%s' % data[2:]
        if self.start == '[]':
            return '[\\]%s' % data[2:]
        return data

    def transform_group(self, data, mark, next):
        return '(%s' % ('|'.join(data[len(self.start):].split(',')))

    def transform_group_close(self, data, mark, next):
        return ')'


def translate(data, sep=os.sep):
    self = BlobTransform(data)
    return ''.join(self)
