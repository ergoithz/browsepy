# -*- coding: UTF-8 -*-

import os
import os.path
import sys
import abc
import time
import shutil
import tempfile
import itertools
import functools
import contextlib
import warnings
import posixpath
import ntpath
import argparse

FS_ENCODING = sys.getfilesystemencoding()
PY_LEGACY = sys.version_info < (3, )
TRUE_VALUES = frozenset(('true', 'yes', '1', 'enable', 'enabled', True, 1))

try:
    import importlib.resources as res  # python 3.7+
except ImportError:
    import importlib_resources as res  # noqa

try:
    from os import scandir as _scandir, walk  # python 3.5+
except ImportError:
    from scandir import scandir as _scandir, walk  # noqa

try:
    from shutil import get_terminal_size  # python 3.3+
except ImportError:
    from backports.shutil_get_terminal_size import get_terminal_size  # noqa

try:
    from queue import Queue, Empty, Full  # python 3
except ImportError:
    from Queue import Queue, Empty, Full  # noqa

try:
    from collections.abc import Iterator as BaseIterator  # python 3.3+
except ImportError:
    from collections import Iterator as BaseIterator  # noqa


class SafeArgumentParser(argparse.ArgumentParser):
    """ArgumentParser based class which safer default behavior."""

    allow_abbrev_support = sys.version_info >= (3, 5, 0)

    def _get_option_tuples(self, option_string):
        return []

    def __init__(self, **kwargs):
        """Initialize object."""
        if self.allow_abbrev_support:
            kwargs.setdefault('allow_abbrev', False)
        kwargs.setdefault('add_help', False)
        super(SafeArgumentParser, self).__init__(**kwargs)


class HelpFormatter(argparse.RawTextHelpFormatter):
    """HelpFormatter for argument parsers honoring terminal width."""

    def __init__(self, prog, indent_increment=2, max_help_position=24,
                 width=None):
        """Initialize object."""
        if width is None:
            try:
                width = get_terminal_size().columns - 2
            except ValueError:  # https://bugs.python.org/issue24966
                pass
        super(HelpFormatter, self).__init__(
            prog, indent_increment, max_help_position, width)


@contextlib.contextmanager
def scandir(path):
    """
    Get iterable of :class:`os.DirEntry` as context manager.

    This is just backwards-compatible :func:`scandir.scandir` context
    manager wrapper, as since `3.6` calling `close` method became
    mandatory, but it's not available on previous versions.

    :param path: path to iterate
    :type path: str
    """
    files = _scandir(path)
    try:
        yield files
    finally:
        if callable(getattr(files, 'close', None)):
            files.close()


def rmtree(path):
    """
    Remove directory tree, with platform-specific fixes.

    A simple :func:`shutil.rmtree` wrapper, with some error handling and
    retry logic, as some filesystems on some platforms does not always
    behave as they should.

    :param path: path to remove
    :type path: str
    """
    attempt = -1
    while os.path.exists(path):
        attempt += 1
        try:
            shutil.rmtree(path)
        except OSError as error:
            if getattr(error, 'winerror', 0) in (5, 145) and attempt < 50:
                time.sleep(0.01)  # allow dumb filesystems to catch up
                continue
            raise


@contextlib.contextmanager
def mkdtemp(suffix='', prefix='', dir=None):
    """
    Create a temporary directory context manager.

    Backwards-compatible :class:`tmpfile.TemporaryDirectory` context
    manager, as it was added on `3.2`.

    :param path: path to iterate
    :type path: str
    """
    path = tempfile.mkdtemp(suffix, prefix, dir)
    try:
        yield path
    finally:
        rmtree(path)


def isexec(path):
    """
    Check if given path points to an executable file.

    :param path: file path
    :type path: str
    :return: True if executable, False otherwise
    :rtype: bool
    """
    return os.path.isfile(path) and os.access(path, os.X_OK)


def fsdecode(path, os_name=os.name, fs_encoding=FS_ENCODING, errors=None):
    """
    Decode given path using filesystem encoding.

    This is necessary as python has pretty bad filesystem support on
    some platforms.

    :param path: path will be decoded if using bytes
    :type path: bytes or str
    :param os_name: operative system name, defaults to os.name
    :type os_name: str
    :param fs_encoding: current filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :return: decoded path
    :rtype: str
    """
    if not isinstance(path, bytes):
        return path
    if not errors:
        use_strict = PY_LEGACY or os_name == 'nt'
        errors = 'strict' if use_strict else 'surrogateescape'
    return path.decode(fs_encoding, errors=errors)


def fsencode(path, os_name=os.name, fs_encoding=FS_ENCODING, errors=None):
    """
    Encode given path using filesystem encoding.

    This is necessary as python has pretty bad filesystem support on
    some platforms.

    :param path: path will be encoded if not using bytes
    :type path: bytes or str
    :param os_name: operative system name, defaults to os.name
    :type os_name: str
    :param fs_encoding: current filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :return: encoded path
    :rtype: bytes
    """
    if isinstance(path, bytes):
        return path
    if not errors:
        use_strict = PY_LEGACY or os_name == 'nt'
        errors = 'strict' if use_strict else 'surrogateescape'
    return path.encode(fs_encoding, errors=errors)


def getcwd(fs_encoding=FS_ENCODING, cwd_fnc=os.getcwd):
    """
    Get current work directory's absolute path.

    Like os.getcwd but garanteed to return an unicode-str object.

    :param fs_encoding: filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :param cwd_fnc: callable used to get the path, defaults to os.getcwd
    :type cwd_fnc: Callable
    :return: path
    :rtype: str
    """
    path = fsdecode(cwd_fnc(), fs_encoding=fs_encoding)
    return os.path.abspath(path)


def getdebug(environ=os.environ, true_values=TRUE_VALUES):
    """
    Get if app is running in debug mode.

    This is detected looking at environment variables.

    :param environ: environment dict-like object
    :type environ: collections.abc.Mapping
    :returns: True if debug contains a true-like string, False otherwise
    :rtype: bool
    """
    return environ.get('DEBUG', '').lower() in true_values


def deprecated(func_or_text, environ=os.environ):
    """
    Decorate function and mark it as deprecated.

    Calling a deprected function will result in a warning message.

    :param func_or_text: message or callable to decorate
    :type func_or_text: callable
    :param environ: optional environment mapping
    :type environ: collections.abc.Mapping
    :returns: nested decorator or new decorated function (depending on params)
    :rtype: callable

    Usage:

    >>> @deprecated
    ... def fnc():
    ...     pass

    Usage (custom message):

    >>> @deprecated('This is deprecated')
    ... def fnc():
    ...     pass

    """
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
                warnings.warn(message, DeprecationWarning, 3)
            return func(*args, **kwargs)
        return new_func
    return inner(func_or_text) if callable(func_or_text) else inner


def usedoc(other):
    """
    Decorator which copies __doc__ of given object into decorated one.

    :param other: anything with a __doc__ attribute
    :type other: any
    :returns: decorator function
    :rtype: callable

    Usage:

    >>> def fnc1():
    ...     \"""docstring\"""
    ...     pass
    >>> @usedoc(fnc1)
    ... def fnc2():
    ...     pass
    >>> fnc2.__doc__
    'docstring'collections.abc.D

    """
    def inner(fnc):
        fnc.__doc__ = fnc.__doc__ or getattr(other, '__doc__')
        return fnc
    return inner


def pathsplit(value, sep=os.pathsep):
    """
    Get enviroment PATH elements as list.

    This function only cares about spliting across OSes.

    :param value: path string, as given by os.environ['PATH']
    :type value: str
    :param sep: PATH separator, defaults to os.pathsep
    :type sep: str
    :yields: every path
    :ytype: str
    """
    for part in value.split(sep):
        if part[:1] == part[-1:] == '"' or part[:1] == part[-1:] == '\'':
            part = part[1:-1]
        yield part


def pathparse(value, sep=os.pathsep, os_sep=os.sep):
    """
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
    """
    escapes = []
    normpath = ntpath.normpath if os_sep == '\\' else posixpath.normpath
    if '\\' not in (os_sep, sep):
        escapes.extend((
            ('\\\\', '<ESCAPE-ESCAPE>', '\\'),
            ('\\"', '<ESCAPE-DQUOTE>', '"'),
            ('\\\'', '<ESCAPE-SQUOTE>', '\''),
            ('\\%s' % sep, '<ESCAPE-PATHSEP>', sep),
            ))
    for original, escape, unescape in escapes:
        value = value.replace(original, escape)
    for part in pathsplit(value, sep=sep):
        if part[-1:] == os_sep and part != os_sep:
            part = part[:-1]
        for original, escape, unescape in escapes:
            part = part.replace(escape, unescape)
        yield normpath(fsdecode(part))


def pathconf(path,
             os_name=os.name,
             isdir_fnc=os.path.isdir,
             pathconf_fnc=getattr(os, 'pathconf', None),
             pathconf_names=getattr(os, 'pathconf_names', ())):
    """
    Get all pathconf variables for given path.

    :param path: absolute fs path
    :type path: str
    :returns: dictionary containing pathconf keys and their values (both str)
    :rtype: dict
    """

    if pathconf_fnc and pathconf_names:
        return {key: pathconf_fnc(path, key) for key in pathconf_names}
    if os_name == 'nt':
        maxpath = 246 if isdir_fnc(path) else 259  # 260 minus <END>
    else:
        maxpath = 255  # conservative sane default
    return {
        'PC_PATH_MAX': maxpath,
        'PC_NAME_MAX': maxpath - len(path),
        }


ENV_PATH = tuple(pathparse(os.getenv('PATH', '')))
ENV_PATHEXT = tuple(pathsplit(os.getenv('PATHEXT', '')))


def which(name,
          env_path=ENV_PATH,
          env_path_ext=ENV_PATHEXT,
          is_executable_fnc=isexec,
          path_join_fnc=os.path.join,
          os_name=os.name):
    """
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
    """
    for path in env_path:
        for suffix in env_path_ext:
            exe_file = path_join_fnc(path, name) + suffix
            if is_executable_fnc(exe_file):
                return exe_file
    return None


def re_escape(pattern, chars=frozenset("()[]{}?*+|^$\\.-#")):
    """
    Escape pattern to include it safely into another regex.

    This function escapes all special regex characters while translating
    non-ascii characters into unicode escape sequences.

    Logic taken from regex module.

    :param pattern: regex pattern to escape
    :type patterm: str
    :returns: escaped pattern
    :rtype: str
    """
    chr_escape = '\\{}'.format
    uni_escape = '\\u{:04d}'.format
    return ''.join(
        chr_escape(c) if c in chars or c.isspace() else
        c if '\x19' < c < '\x80' else
        uni_escape(ord(c))
        for c in pattern
        )


if PY_LEGACY:
    class FileNotFoundError(BaseException):
        __metaclass__ = abc.ABCMeta

    FileNotFoundError.register(OSError)
    FileNotFoundError.register(IOError)

    class Iterator(BaseIterator):
        def next(self):
            """
            Call :method:`__next__` for compatibility.

            :returns: see :method:`__next__`
            """
            return self.__next__()

    range = xrange  # noqa
    filter = itertools.ifilter
    map = itertools.imap
    basestring = basestring  # noqa
    unicode = unicode  # noqa
    chr = unichr  # noqa
    bytes = str  # noqa
else:
    FileNotFoundError = FileNotFoundError
    Iterator = BaseIterator
    range = range
    filter = filter
    map = map
    basestring = str
    unicode = str
    chr = chr
    bytes = bytes

NoneType = type(None)
