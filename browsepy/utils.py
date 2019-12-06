"""Small utility functions for common tasks."""

import sys
import os
import os.path
import random
import functools
import contextlib
import collections

import flask


def ppath(*args, **kwargs):
    """
    Join given path components relative to a module location.

    :param module: Module name
    :type module: str
    """
    module = get_module(kwargs.pop('module', __name__))
    if kwargs:
        raise TypeError(
            'ppath() got an unexpected keyword argument \'%s\''
            % next(iter(kwargs))
            )
    path = os.path.realpath(module.__file__)
    return os.path.join(os.path.dirname(path), *args)


@contextlib.contextmanager
def dummy_context():
    """Get a dummy context manager."""
    yield


def get_module(name):
    """
    Get module object by name.

    :param name: module name
    :type name: str
    :return: module or None if not found
    :rtype: module or None
    """
    __import__(name)
    return sys.modules.get(name, None)


def random_string(size, sample=tuple(map(chr, range(256)))):
    """
    Get random string of given size.

    :param size: length of the returned string
    :type size: int
    :param sample: character space, defaults to full 8-bit utf-8
    :type sample: tuple of str
    :returns: random string of specified size
    :rtype: str
    """
    randrange = functools.partial(random.randrange, 0, len(sample))
    return ''.join(sample[randrange()] for i in range(size))


def solve_local(context_local):
    """
    Resolve given context local to its actual value.

    If given object isn't a context local, nothing happens, return the
    same object.
    """
    if callable(getattr(context_local, '_get_current_object', None)):
        return context_local._get_current_object()
    return context_local


def clear_localstack(stack):
    """
    Clear given werkzeug LocalStack instance.

    :param ctx: local stack instance
    :type ctx: werkzeug.local.LocalStack
    """
    while stack.pop():
        pass


def clear_flask_context():
    """
    Clear flask current_app and request globals.

    When using :meth:`flask.Flask.test_client`, even as context manager,
    the flask's globals :attr:`flask.current_app` and :attr:`flask.request`
    are left dirty, so testing code relying on them will probably fail.

    This function clean said globals, and should be called after testing
    with :meth:`flask.Flask.test_client`.
    """
    clear_localstack(flask._app_ctx_stack)
    clear_localstack(flask._request_ctx_stack)


def defaultsnamedtuple(name, fields, defaults=None):
    """
    Generate namedtuple with default values.

    This somewhat tries to mimic py3.7 namedtuple with keyword-based
    defaults, in a backwards-compatible way.

    :param name: name
    :param fields: iterable with field names
    :param defaults: iterable or mapping with field defaults
    :returns: defaultdict with given fields and given defaults
    :rtype: collections.defaultdict
    """
    nt = collections.namedtuple(name, fields)
    nt.__new__.__defaults__ = (None, ) * len(fields)
    nt.__module__ = __name__
    if defaults:
        nt.__new__.__defaults__ = tuple(
            nt(**defaults)
            if isinstance(defaults, collections.Mapping) else
            nt(*defaults)
            )
    return nt
