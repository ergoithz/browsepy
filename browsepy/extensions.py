import re

import jinja2
import jinja2.ext
import jinja2.lexer

from browsepy.transform import StateMachine


class SGMLCompressContext(StateMachine):
    re_whitespace = re.compile('[ \\t\\r\\n]+')
    token_class = jinja2.lexer.Token
    block_tokens = {
        'variable_begin': 'variable_end',
        'block_begin': 'block_end'
        }
    block_tags = {}  # block content will be treated as literal text
    jumps = {  # state machine jumps
        'text': {
            '<': 'tag',
            '<!--': 'comment',
            '<![CDATA[': 'cdata',
            },
        'lit1': {'"': 'tag'},
        'lit2': ("'", 'tag'),
        'tag': {
            '>': 'text',
            '"': 'lit1',
            "'": 'lit2'
            },
        'comment': {'-->': 'text'},
        'cdata': {']]>': 'text'}
        }
    lineno = 0  # current token lineno
    skip_until_token = None  # inside token until this is met
    skip_until_text = None  # inside text until this is met
    current = 'text'

    def look(self, value, current, start):
        offset = len(start)
        if self.skip_until_text and current == 'text':
            mark = self.skip_until_text
            index = value.find(mark, offset)
            if -1 != index:
                yield index, mark, current
        else:
            super_look = super(SGMLCompressContext, self).look
            for result in super_look(value, current, start):
                yield result
        yield len(value), '', None

    def finalize(self):
        for data in super(SGMLCompressContext, self).finalize():
            yield self.token_class(self.lineno, 'data', data)

    def transform_tag(self, data, current, start, partial=False):
        tagstart = start == '<'
        data = self.re_whitespace.sub(' ', data[1:] if tagstart else data)
        if tagstart:
            data = data.lstrip() if partial else data.strip()
            tagname = data.split(' ', 1)[0]
            self.skip_until_text = self.block_tags.get(tagname)
            return '<' + data
        elif partial:
            return data.rstrip()
        return start if data.strip() == start else data

    def transform_text(self, data, current, start, partial=False):
        if not self.skip_until_text:
            return start if data.strip() == start else data
        elif not partial:
            self.skip_until_text = None
        return data

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
        lineno = token.lineno
        self.pending += token.value
        pending_size = len(self.pending)
        for data in self:
            self.lineno = lineno if size > pending_size else self.lineno
            yield self.token_class(self.lineno, 'data', data)
            pending_size = len(self.pending)


class HTMLCompressContext(SGMLCompressContext):
    block_tags = {
        'textarea': '</textarea>',
        'pre': '</pre>',
        'script': '</script>',
        'style': '</style>',
        }


class HTMLCompress(jinja2.ext.Extension):
    context_class = HTMLCompressContext

    def filter_stream(self, stream):
        feed = self.context_class()
        for token in stream:
            for data in feed.feed(token):
                yield data
        for data in feed.finalize():
            yield data
