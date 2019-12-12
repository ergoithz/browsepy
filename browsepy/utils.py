"""Small utility functions for common tasks."""

import collections

import flask


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
