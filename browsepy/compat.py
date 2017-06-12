#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import sys
import itertools

import warnings
import functools

FS_ENCODING = sys.getfilesystemencoding()
PY_LEGACY = sys.version_info < (3, )
TRUE_VALUES = frozenset(('true', 'yes', '1', 'enable', 'enabled', True, 1))

try:
    from os import scandir, walk
except ImportError:
    from scandir import scandir, walk  # noqa

try:
    from shutil import get_terminal_size
except ImportError:
    from backports.shutil_get_terminal_size import get_terminal_size  # noqa


def isexec(path):
    '''
    Check if given path points to an executable file.

    :param path: file path
    :type path: str
    :return: True if executable, False otherwise
    :rtype: bool
    '''
    return os.path.isfile(path) and os.access(path, os.X_OK)


def fsdecode(path, os_name=os.name, fs_encoding=FS_ENCODING, errors=None):
    '''
    Decode given path.

    :param path: path will be decoded if using bytes
    :type path: bytes or str
    :param os_name: operative system name, defaults to os.name
    :type os_name: str
    :param fs_encoding: current filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :return: decoded path
    :rtype: str
    '''
    if not isinstance(path, bytes):
        return path
    if not errors:
        use_strict = PY_LEGACY or os_name == 'nt'
        errors = 'strict' if use_strict else 'surrogateescape'
    return path.decode(fs_encoding, errors=errors)


def fsencode(path, os_name=os.name, fs_encoding=FS_ENCODING, errors=None):
    '''
    Encode given path.

    :param path: path will be encoded if not using bytes
    :type path: bytes or str
    :param os_name: operative system name, defaults to os.name
    :type os_name: str
    :param fs_encoding: current filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :return: encoded path
    :rtype: bytes
    '''
    if isinstance(path, bytes):
        return path
    if not errors:
        use_strict = PY_LEGACY or os_name == 'nt'
        errors = 'strict' if use_strict else 'surrogateescape'
    return path.encode(fs_encoding, errors=errors)


def getcwd(fs_encoding=FS_ENCODING, cwd_fnc=os.getcwd):
    '''
    Get current work directory's absolute path.
    Like os.getcwd but garanteed to return an unicode-str object.

    :param fs_encoding: filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :param cwd_fnc: callable used to get the path, defaults to os.getcwd
    :type cwd_fnc: Callable
    :return: path
    :rtype: str
    '''
    path = fsdecode(cwd_fnc(), fs_encoding=fs_encoding)
    return os.path.abspath(path)


def getdebug(environ=os.environ, true_values=TRUE_VALUES):
    '''
    Get if app is expected to be ran in debug mode looking at environment
    variables.

    :param environ: environment dict-like object
    :type environ: collections.abc.Mapping
    :returns: True if debug contains a true-like string, False otherwise
    :rtype: bool
    '''
    return environ.get('DEBUG', '').lower() in true_values


def deprecated(func_or_text, environ=os.environ):
    '''
    Decorator used to mark functions as deprecated. It will result in a
    warning being emmitted hen the function is called.

    Usage:

    >>> @deprecated
    ... def fnc():
    ...     pass

    Usage (custom message):

    >>> @deprecated('This is deprecated')
    ... def fnc():
    ...     pass

    :param func_or_text: message or callable to decorate
    :type func_or_text: callable
    :param environ: optional environment mapping
    :type environ: collections.abc.Mapping
    :returns: nested decorator or new decorated function (depending on params)
    :rtype: callable
    '''
    def inner(func):
        message = (
            'Deprecated function {}.'.format(func.__name__)
            if callable(func_or_text) else
            func_or_text
            )

        @functools.wraps(func)
        def new_func(*args, **kwargs):
            with warnings.catch_warnings():
                if getdebug(environ):
                    warnings.simplefilter('always', DeprecationWarning)
                warnings.warn(message, category=DeprecationWarning,
                              stacklevel=3)
            return func(*args, **kwargs)
        return new_func
    return inner(func_or_text) if callable(func_or_text) else inner


def usedoc(other):
    '''
    Decorator which copies __doc__ of given object into decorated one.

    Usage:

    >>> def fnc1():
    ...     """docstring"""
    ...     pass
    >>> @usedoc(fnc1)
    ... def fnc2():
    ...     pass
    >>> fnc2.__doc__
    'docstring'collections.abc.D

    :param other: anything with a __doc__ attribute
    :type other: any
    :returns: decorator function
    :rtype: callable
    '''
    def inner(fnc):
        fnc.__doc__ = fnc.__doc__ or getattr(other, '__doc__')
        return fnc
    return inner


def pathsplit(value, sep=os.pathsep):
    '''
    Get enviroment PATH elements as list.

    This function only cares about spliting across OSes.

    :param value: path string, as given by os.environ['PATH']
    :type value: str
    :param sep: PATH separator, defaults to os.pathsep
    :type sep: str
    :yields: every path
    :ytype: str
    '''
    for part in value.split(sep):
        if part[:0] == part[-1:] == '"' or part[:0] == part[-1:] == '\'':
            part = part[1:-1]
        yield part


def pathparse(value, sep=os.pathsep, os_sep=os.sep):
    '''
    Get enviroment PATH directories as list.

    This function cares about spliting, escapes and normalization of paths
    across OSes.

    :param value: path string, as given by os.environ['PATH']
    :type value: str
    :param sep: PATH separator, defaults to os.pathsep
    :type sep: str
    :param os_sep: OS filesystem path separator, defaults to os.sep
    :type os_sep: str
    :yields: every path
    :ytype: str
    '''
    escapes = []
    if '\\' not in (os_sep, sep):
        escapes.extend((
            ('\\\\', '<ESCAPE-ESCAPE>'),
            ('\\"', '<ESCAPE-DQUOTE>'),
            ('\\\'', '<ESCAPE-SQUOTE>'),
            ('\\%s' % sep, '<ESCAPE-PATHSEP>'),
            ))
    for original, escape in escapes:
        value = value.replace(original, escape)
    for part in pathsplit(value, sep=sep):
        if part[-1:] == os_sep:
            part = part[:-1]
        for original, escape in escapes:
            part = part.replace(escape, original)
        yield os.path.normpath(fsdecode(part))


ENV_PATH = tuple(pathparse(os.getenv('PATH', '')))
ENV_PATHEXT = tuple(pathsplit(os.getenv('PATHEXT', '')))


def which(name,
          env_path=ENV_PATH,
          env_path_ext=ENV_PATHEXT,
          is_executable_fnc=isexec,
          path_join_fnc=os.path.join,
          os_name=os.name):
    '''
    Get command absolute path.

    :param name: name of executable command
    :type name: str
    :param env_path: OS environment executable paths, defaults to autodetected
    :type env_path: list of str
    :param is_executable_fnc: callable will be used to detect if path is
                              executable, defaults to `isexec`
    :type is_executable_fnc: Callable
    :param path_join_fnc: callable will be used to join path components
    :type path_join_fnc: Callable
    :param os_name: os name, defaults to os.name
    :type os_name: str
    :return: absolute path
    :rtype: str or None
    '''
    for path in env_path:
        for suffix in env_path_ext:
            exe_file = path_join_fnc(path, name) + suffix
            if is_executable_fnc(exe_file):
                return exe_file
    return None


def re_escape(pattern, chars=frozenset("()[]{}?*+|^$\\.-#")):
    '''
    Escape all special regex characters in pattern.
    Logic taken from regex module.

    :param pattern: regex pattern to escape
    :type patterm: str
    :returns: escaped pattern
    :rtype: str
    '''
    escape = '\\{}'.format
    return ''.join(
        escape(c) if c in chars or c.isspace() else
        '\\000' if c == '\x00' else c
        for c in pattern
        )


if PY_LEGACY:
    FileNotFoundError = OSError  # noqa
    range = xrange  # noqa
    filter = itertools.ifilter
    basestring = basestring  # noqa
    unicode = unicode  # noqa
    chr = unichr  # noqa
    bytes = str  # noqa
else:
    FileNotFoundError = FileNotFoundError
    range = range
    filter = filter
    basestring = str
    unicode = str
    chr = chr
    bytes = bytes
