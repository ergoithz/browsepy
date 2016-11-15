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

    def __init__(self):
        self.intag = False
        self.pending = ''
        self.lineno = 0
        self.skip_until = None

    def finalize(self, strip=False):
        if self.intag:
            data = self._collapse(self.pending)
        else:
            data = self.pending.rstrip() if strip else self.pending
        if data.strip():
            yield self.token_class(self.lineno, 'data', data)
        self.pending = ''

    def _collapse(self, data):
        return self.re_whitespace.sub(
            lambda m: ' ' if m.groups()[-1] else m.group(0),
            data
            )

    def feed(self, token):
        if self.skip_until:
            yield token
            if token.type == self.skip_until:
                self.skip_until = None
            return

        if token.type in self.block_tokens:
            print(token.type)
            for data in self.finalize(token.type == 'block_begin'):
                yield data
            yield token
            self.skip_until = self.block_tokens[token.type]
            return

        lineno = self.lineno
        size = len(token.value)
        value = self.pending + token.value
        while value:
            lineno = self.lineno if len(value) > size else token.lineno
            s, p, value = value.partition('>' if self.intag else '<')
            if self.intag:
                s = self._collapse(s)
                if p:
                    self.intag = False
                    s = s.rstrip() + p
                yield self.token_class(lineno, 'data', s)
            elif p:
                self.intag = True
                s = s + p if s.strip() else p
                yield self.token_class(lineno, 'data', s)
            else:
                value = s
                break
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
