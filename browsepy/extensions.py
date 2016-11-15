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
    block_tags = {
        'textarea': '</textarea>',
        'pre': '</textarea>',
        'script': '</script>',
        'style': '</script>',
        }
    block_text = {
        '<![CDATA[': ']]>'
        }
    jumps = {
        '': {'<': '<'},   # text
        '"': {'"': '<'},  # attr-value
        "'": ("'", '<'),  # attr-value
        '<': {            # tag
            '>': '',
            '"': '"',
            "'": "'"
            },
        }

    def __init__(self):
        self.current = ''
        self.pending = ''
        self.lineno = 0
        self.skip_until_token = None
        self.skip_until_substring = None

    def finalize(self, strip=False):
        if self.pending.strip():
            data = self._minify(self.pending, self.current, True)
            yield self.token_class(self.lineno, 'data', data)
        self.pending = ''

    def _minify(self, data, current, incomplete=False):
        if current == '<':
            for name, until in self.block_tags.items():
                if data.startswith(name):
                    self.skip_until_substring = until
                    break
            last = self.re_whitespace.groups
            return self.re_whitespace.sub(
                lambda m: ' ' if m.group(last) else m.group(0),
                data.rstrip()
                )
        elif current == '':
            prefix = ''
            if self.skip_until_substring:
                substring = self.skip_until_substring
                if substring in data:
                    self.skip_until_substring = None
                    index = data.index(substring) + len(substring)
                    prefix = data[:index]
                    data = data[index:]
                else:
                    prefix = data
                    data = ''
            return prefix + (data if data.strip() else '')
        return data

    def _next(self, data, current):
        endmark = None
        endnext = None
        endindex = len(data) + 1
        for mark, next in self.jumps[current].items():
            index = data.find(mark)
            if -1 < index < endindex:
                endmark = mark
                endnext = next
                endindex = index
        return endmark, endindex, endnext

    def _process(self, lineno, value, current):
        endmark, endindex, endnext = self._next(value, current)
        if endmark:
            s = self._minify(value[:endindex], current) + endmark
            yield s, value[endindex + len(endmark):], endnext

    def feed(self, token):
        if self.skip_until_token:
            yield token
            if token.type == self.skip_until_token:
                self.skip_until_token = None
        elif token.type in self.block_tokens:
            for data in self.finalize(token.type == 'block_begin'):
                yield data
            yield token
            self.skip_until_token = self.block_tokens[token.type]
        else:
            size = len(token.value)
            lno = self.lineno
            value = self.pending + token.value
            current = self.current
            loop = True
            while loop:
                loop = False
                lno = self.lineno if len(value) > size else token.lineno
                for data, value, current in self._process(lno, value, current):
                    loop = value
                    self.token_class(lno, 'data', data)
            self.lineno = lno
            self.pending = value
            self.current = current


class HTMLCompress(jinja2.ext.Extension):
    def filter_stream(self, stream):
        feed = HTMLCompressFeed()
        for token in stream:
            for data in feed.feed(token):
                yield data
        for data in feed.finalize():
            yield data
