import re

import jinja2
import jinja2.ext
import jinja2.lexer


class HTMLCompressFeed(object):
    re_whitespace = re.compile('[ \\t\\r\\n]+')
    token_class = jinja2.lexer.Token
    block_tokens = {
        'variable_begin': 'variable_end',
        'block_begin': 'block_end'
        }
    block_tags = {
        'textarea': '</textarea>',
        'pre': '</pre>',
        'script': '</script>',
        'style': '</style>',
        }
    block_text = {
        '<![CDATA[': ']]>'
        }
    jumps = {
        'text': {'<': 'tag'},
        'lit1': {'"': 'tag'},
        "lit2": ("'", 'tag'),
        'tag': {
            '>': 'text',
            '"': 'lit1',
            "'": 'lit2'
            },
        }

    def __init__(self):
        self.start = ''  # character which started current stae
        self.current = 'text'  # current state
        self.pending = ''  # buffer of current state data
        self.lineno = 0  # current token lineno
        self.skip_until_token = None  # inside token until this is met
        self.skip_until_tag = None  # inside literal tag until this is met

    def finalize(self):
        if self.pending:
            data = self._minify(self.pending, self.current, self.start, True)
            yield self.token_class(self.lineno, 'data', data)
        self.start = ''
        self.pending = ''

    def _minify(self, data, current, start, partial=False):
        if current == 'tag':
            tagstart = start == '<'
            data = self.re_whitespace.sub(' ', data[1:] if tagstart else data)
            if tagstart:
                data = data.lstrip() if partial else data.strip()
                tagname = data.split(' ', 1)[0]
                self.skip_until_tag = self.block_tags.get(tagname)
                return '<' + data
            elif partial:
                return data.rstrip()
            return start if data.strip() == start else data
        elif current == 'text' and not self.skip_until_tag:
            return start if data.strip() == start else data
        return data

    def _next(self, data, current, start):
        endmark = None
        endnext = None
        endindex = len(data) + 1
        endindexstart = len(start)
        for mark, next in self.jumps[current].items():
            index = data.find(mark, endindexstart)
            if -1 < index < endindex:
                endmark = mark
                endnext = next
                endindex = index
        return endmark, endindex, endnext

    def _process(self, lineno, value, current, start):
        endmark, endindex, endnext = self._next(value, current, start)
        if endmark:
            s = self._minify(value[:endindex], current, start)
            yield s, value[endindex:], endnext, endmark

    def feed(self, token):
        if self.skip_until_token:
            yield token
            if token.type == self.skip_until_token:
                self.skip_until_token = None
            return

        if token.type in self.block_tokens:
            for data in self.finalize():
                yield data
            yield token
            self.skip_until_token = self.block_tokens[token.type]
            return

        size = len(token.value)
        start = self.start
        lno = self.lineno
        val = self.pending + token.value
        curr = self.current
        loop = val
        while loop:
            loop = None
            lno = self.lineno if len(val) > size else token.lineno
            for data, val, curr, start in self._process(lno, val, curr, start):
                yield self.token_class(lno, 'data', data)
                loop = val
        self.start = start
        self.lineno = lno
        self.pending = val
        self.current = curr


class HTMLCompress(jinja2.ext.Extension):
    def filter_stream(self, stream):
        feed = HTMLCompressFeed()
        for token in stream:
            for data in feed.feed(token):
                yield data
        for data in feed.finalize():
            yield data
