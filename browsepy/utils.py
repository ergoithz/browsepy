# -*- coding: UTF-8 -*-

import sys
import os
import os.path
import re
import random
import functools
import collections

import flask


re_words = re.compile(r'\b((?:[._]+|\w)+)\b')


def ppath(*args, **kwargs):
    '''
    Get joined file path relative to module location.

    :param module: Module name
    :type module: str
    '''
    module = get_module(kwargs.pop('module', __name__))
    if kwargs:
        raise TypeError(
            'ppath() got an unexpected keyword argument \'%s\''
            % next(iter(kwargs))
            )
    path = os.path.realpath(module.__file__)
    return os.path.join(os.path.dirname(path), *args)


def get_module(name):
    '''
    Get module object by name.

    :param name: module name
    :type name: str
    :return: module or None if not found
    :rtype: module or None
    '''
    try:
        __import__(name)
        return sys.modules[name]
    except ImportError as error:
        message = error.args[0] if error.args else ''
        words = frozenset(re_words.findall(message))
        parts = name.split('.')
        for i in range(len(parts) - 1, -1, -1):
            if '.'.join(parts[i:]) in words:
                return None
        raise


def random_string(size, sample=tuple(map(chr, range(256)))):
    '''
    Get random string of given size.

    :param size: length of the returned string
    :type size: int
    :param sample: character space, defaults to full 8-bit utf-8
    :type sample: tuple of str
    :returns: random string of specified size
    :rtype: str
    '''
    randrange = functools.partial(random.randrange, 0, len(sample))
    return ''.join(sample[randrange()] for i in range(size))


def solve_local(context_local):
    '''
    Resolve given context local to its actual value. If given object
    it's not a context local nothing happens, just returns the same value.
    '''
    if callable(getattr(context_local, '_get_current_object', None)):
        return context_local._get_current_object()
    return context_local


def stream_template(template_name, **context):
    '''
    Some templates can be huge, this function returns an streaming response,
    sending the content in chunks and preventing from timeout.

    :param template_name: template
    :param **context: parameters for templates.
    :yields: HTML strings
    :rtype: Iterator of str
    '''
    app = solve_local(context.get('current_app') or flask.current_app)
    app.update_template_context(context)
    template = app.jinja_env.get_template(template_name)
    stream = template.generate(context)
    return flask.Response(flask.stream_with_context(stream))


def clear_localstack(stack):
    '''
    Clear given werkzeug LocalStack instance.

    :param ctx: local stack instance
    :type ctx: werkzeug.local.LocalStack
    '''
    while stack.pop():
        pass


def clear_flask_context():
    '''
    Clear flask current_app and request globals.

    When using :meth:`flask.Flask.test_client`, even as context manager,
    the flask's globals :attr:`flask.current_app` and :attr:`flask.request`
    are left dirty, so testing code relying on them will probably fail.

    This function clean said globals, and should be called after testing
    with :meth:`flask.Flask.test_client`.
    '''
    clear_localstack(flask._app_ctx_stack)
    clear_localstack(flask._request_ctx_stack)


def defaultsnamedtuple(name, fields, defaults=None):
    '''
    Generate namedtuple with default values.

    :param name: name
    :param fields: iterable with field names
    :param defaults: iterable or mapping with field defaults
    :returns: defaultdict with given fields and given defaults
    :rtype: collections.defaultdict
    '''
    nt = collections.namedtuple(name, fields)
    nt.__new__.__defaults__ = (None, ) * len(nt._fields)
    if isinstance(defaults, collections.Mapping):
        nt.__new__.__defaults__ = tuple(nt(**defaults))
    elif defaults:
        nt.__new__.__defaults__ = tuple(nt(*defaults))
    return nt
