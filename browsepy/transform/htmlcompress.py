import re

import jinja2
import jinja2.ext
import jinja2.lexer

from . import StateMachine


class SGMLCompressContext(StateMachine):
    re_whitespace = re.compile('[ \\t\\r\\n]+')
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
    skip_until_text = None  # inside text until this is met
    current = 'text'

    @property
    def nearest(self):
        if self.skip_until_text and self.current == 'text':
            mark = self.skip_until_text
            index = self.pending.find(mark, len(self.start))
            if index == -1:
                return len(self.pending), '', None
            return index, mark, self.current
        return super(SGMLCompressContext, self).nearest

    def transform_tag(self, data, mark, next):
        tagstart = self.start == '<'
        data = self.re_whitespace.sub(' ', data[1:] if tagstart else data)
        if tagstart:
            data = data.lstrip() if next is None else data.strip()
            tagname = data.split(' ', 1)[0]
            self.skip_until_text = self.block_tags.get(tagname)
            return '<' + data
        elif next is None:
            return data.rstrip()
        return self.start if data.strip() == self.start else data

    def transform_text(self, data, mark, next):
        if not self.skip_until_text:
            return self.start if data.strip() == self.start else data
        elif next is not None:
            self.skip_until_text = None
        return data


class HTMLCompressContext(SGMLCompressContext):
    block_tags = {
        'textarea': '</textarea>',
        'pre': '</pre>',
        'script': '</script>',
        'style': '</style>',
        }


class HTMLCompress(jinja2.ext.Extension):
    context_class = HTMLCompressContext
    token_class = jinja2.lexer.Token
    block_tokens = {
        'variable_begin': 'variable_end',
        'block_begin': 'block_end'
        }

    def filter_stream(self, stream):
        transform = self.context_class()
        lineno = 0
        skip_until_token = None
        for token in stream:
            if skip_until_token:
                yield token
                if token.type == skip_until_token:
                    skip_until_token = None
                continue

            if token.type != 'data':
                for data in transform.finish():
                    yield self.token_class(lineno, 'data', data)
                yield token
                skip_until_token = self.block_tokens.get(token.type)
                continue

            if not transform.pending:
                lineno = token.lineno

            for data in transform.feed(token.value):
                yield self.token_class(lineno, 'data', data)
                lineno = token.lineno

        for data in transform.finish():
            yield self.token_class(lineno, 'data', data)
