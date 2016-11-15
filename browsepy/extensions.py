import re

import jinja2
import jinja2.ext
import jinja2.lexer


class HTMLCompressFeed(object):
    re_whitespace = re.compile('(\"[^\"\\n]*\"|\'[^\'\\n]*\')|([ \\t\\r\\n]+)')
    token_class = jinja2.lexer.Token
    block_tokens = {
        'variable_begin': 'variable_end',
        'block_begin': 'block_end'
        }
    ignore_elements = ['textarea', 'pre', 'script', 'style']

    def __init__(self):
        self.intag = False
        self.pending = ''
        self.lineno = 0
        self.skip_until = None
        self.ignore_until = None

    def finalize(self, strip=False):
        if self.intag:
            data = self._collapse(self.pending)
        elif self.ignore_until:
            data = self.pending
        else:
            data = self.pending.rstrip() if strip else self.pending
        if data.strip():
            yield self.token_class(self.lineno, 'data', data)
        self.pending = ''

    def _collapse(self, data):
        last = self.re_whitespace.groups
        return self.re_whitespace.sub(
            lambda m: ' ' if m.group(last) else m.group(0),
            data
            )

    def _process(self, value, lineno):
        if self.intag:
            s, p, value = value.partition('>')
            s = self._collapse(s)
            if p:
                self.intag = False
                s = s.rstrip() + p
            yield self.token_class(lineno, 'data', s), value
        elif self.ignore_until:
            s, p, value = value.partition(self.ignore_until)
            if p:
                self.intag = False
                self.ignore_until = None
                s = s + p
            yield self.token_class(lineno, 'data', s), value
        else:
            s, p, value = value.partition('<')
            if p:
                self.intag = True
                s = s + p if s.strip() else p
                yield self.token_class(lineno, 'data', s), value
                for elm in self.ignore_elements:
                    if value.startswith(elm):
                        self.ignore_until = '</{}>'.format(elm)
                        break

    def feed(self, token):
        if self.skip_until:
            yield token
            if token.type == self.skip_until:
                self.skip_until = None
        elif token.type in self.block_tokens:
            for data in self.finalize(token.type == 'block_begin'):
                yield data
            yield token
            self.skip_until = self.block_tokens[token.type]
        else:
            lineno = self.lineno
            size = len(token.value)
            value = self.pending + token.value
            loop = True
            while loop:
                loop = False
                lineno = self.lineno if len(value) > size else token.lineno
                for data, value in self._process(value, lineno):
                    loop = value
                    yield data
            self.lineno = lineno
            self.pending = value


class HTMLCompress(jinja2.ext.Extension):
    def filter_stream(self, stream):
        feed = HTMLCompressFeed()
        for token in stream:
            for data in feed.feed(token):
                yield data
        for data in feed.finalize():
            yield data
