"""Module providing HTML compression extension jinja2."""

import re
import functools

import jinja2
import jinja2.ext
import jinja2.lexer

from . import StateMachine


class OriginalContext:
    """Non-minifying context stub class."""

    def feed(self, token):
        """Add token to context an yield tokens."""
        yield token

    def finish(self):
        """Finish context and yield tokens."""
        return
        yield


class MinifyContext(StateMachine):
    """Base minifying jinja2 template token finite state machine."""

    token_class = jinja2.lexer.Token
    block_tokens = {
        'variable_begin': 'variable_end',
        'block_begin': 'block_end'
        }
    skip_until_token = None
    lineno = 0

    def feed(self, token):
        """Process a single token, yielding processed ones."""
        if self.skip_until_token:
            yield token
            if token.type == self.skip_until_token:
                self.skip_until_token = None
        elif token.type != 'data':
            for ftoken in self.finish():
                yield ftoken
            yield token
            self.skip_until_token = self.block_tokens.get(token.type)
        else:
            if not self.pending:
                self.lineno = token.lineno

            for data in super().feed(token.value):
                yield self.token_class(self.lineno, 'data', data)
                self.lineno = token.lineno

    def finish(self):
        """Set state machine as finished, yielding remaining tokens."""
        for data in super().finish():
            yield self.token_class(self.lineno, 'data', data)


class SGMLMinifyContext(MinifyContext):
    """Minifying context for jinja2 SGML templates."""

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
        """Get next data chunk to be processed."""
        if self.skip_until_text and self.current == 'text':
            mark = self.skip_until_text
            index = self.pending.find(mark, len(self.start))
            if index == -1:
                return len(self.pending), '', None
            return index, mark, self.current
        return super().nearest

    def transform_tag(self, data, mark, next):
        """Minify SML tag node."""
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
        """Minify SGML text node."""
        if not self.skip_until_text:
            return self.start if data.strip() == self.start else data
        elif next is not None:
            self.skip_until_text = None
        return data


class HTMLMinifyContext(SGMLMinifyContext):
    """Minifying context for jinja2 HTML templates."""

    block_tags = {
        'textarea': '</textarea>',
        'pre': '</pre>',
        'script': '</script>',
        'style': '</style>',
        }


class JSMinifyContext(MinifyContext):
    """Minifying context for jinja2 JavaScript templates."""

    jumps = {
        'code': {
            '\'': 'single_string',
            '"': 'double_string',
            '//': 'line_comment',
            '/*': 'multiline_comment',
            },
        'single_string': {
            '\'': 'code',
            '\\': 'single_string_escape',
            },
        'single_string_escape': {
            c: 'single_string' for c in ('\\', '\'', '')
            },
        'double_string': {
            '"': 'code',
            '\\': 'double_string_escape',
            },
        'double_string_escape': {
            c: 'double_string' for c in ('\\', '"', '')
            },
        'line_comment': {
            '\n': 'ignore',
            },
        'multiline_comment': {
            '*/': 'ignore',
            },
        'ignore': {
            '': 'code',
            }
        }
    current = 'code'
    pristine = True
    strip_tokens = staticmethod(
        functools.partial(
            re.compile(r'\s+[^\w\d\s]\s*|[^\w\d\s]\s+|\s{2,}').sub,
            lambda x: x.group(0).strip() or ' '
            )
        )

    def transform_code(self, data, mark, next):
        """Minify JS-like code."""
        if self.pristine:
            data = data.lstrip()
            self.pristine = False
        return self.strip_tokens(data)

    def transform_ignore(self, data, mark, next):
        """Ignore text."""
        self.pristine = True
        return ''

    transform_line_comment = transform_ignore
    transform_multiline_comment = transform_ignore


class MinifyExtension(jinja2.ext.Extension):
    """Jinja2 template minifying extension."""

    default_context_class = OriginalContext
    context_classes = {
        '.xml': SGMLMinifyContext,
        '.xhtml': HTMLMinifyContext,
        '.html': HTMLMinifyContext,
        '.htm': HTMLMinifyContext,
        '.json': JSMinifyContext,
        '.js': JSMinifyContext,
        }

    def get_context(self, filename=None):
        """Get minifying context based on given filename."""
        if filename:
            for extension, context_class in self.context_classes.items():
                if filename.endswith(extension):
                    return context_class()
        return self.default_context_class()

    def filter_stream(self, stream):
        """Yield minified tokens from :class:`~jinja2.lexer.TokenStream`."""
        transform = self.get_context(stream.name)
        for token in stream:
            yield from transform.feed(token)
        yield from transform.finish()
