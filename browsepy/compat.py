"""Module providing both runtime and platform compatibility workarounds."""

import typing
import os
import os.path
import sys
import errno
import time
import functools
import contextlib
import warnings
import posixpath
import ntpath
import argparse
import shutil

try:
    import importlib.resources as res  # python 3.7+
except ImportError:
    import importlib_resources as res  # noqa

try:
    from functools import cached_property   # python 3.8+
except ImportError:
    from werkzeug.utils import cached_property  # noqa


TFunction = typing.Callable[..., typing.Any]
TFunction2 = typing.Callable[..., typing.Any]
OSEnvironType = typing.Mapping[str, str]
FS_ENCODING = sys.getfilesystemencoding()
TRUE_VALUES = frozenset(
    # Truthy values
    ('true', 'yes', '1', 'enable', 'enabled', True, 1)
    )
RETRYABLE_OSERROR_PROPERTIES = {
    'errno': frozenset(
        # Error codes which could imply a busy filesystem
        getattr(errno, prop)
        for prop in (
            'ENOENT',
            'EIO',
            'ENXIO',
            'EAGAIN',
            'EBUSY',
            'ENOTDIR',
            'EISDIR',
            'ENOTEMPTY',
            'EALREADY',
            'EINPROGRESS',
            'EREMOTEIO',
            )
        if hasattr(errno, prop)
        ),
    'winerror': frozenset(
        # Handle WindowsError instances without errno
        (5, 145)
        ),
    }


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
        """Initialize."""
        if width is None:
            try:
                width = shutil.get_terminal_size().columns - 2
            except ValueError:  # https://bugs.python.org/issue24966
                pass
        super(HelpFormatter, self).__init__(
            prog, indent_increment, max_help_position, width)


@contextlib.contextmanager
def scandir(path):
    # type: (str) -> typing.Generator[typing.Iterator[os.DirEntry], None, None]
    """
    Get iterable of :class:`os.DirEntry` as context manager.

    This is just backwards-compatible :func:`scandir.scandir` context
    manager wrapper, as since `3.6` calling `close` method became
    mandatory, but it's not available on previous versions.

    :param path: path to iterate
    :type path: str
    """
    files = os.scandir(path)
    try:
        yield files
    finally:
        if callable(getattr(files, 'close', None)):
            files.close()


def _unsafe_rmtree(path):
    # type: (str) -> None
    """
    Remove directory tree, without error handling.

    :param path: directory path
    :type path: str
    """
    for base, dirs, files in os.walk(path, topdown=False):
        for filename in files:
            os.remove(os.path.join(base, filename))

        with scandir(base) as remaining:
            retry = any(remaining)

        if retry:
            time.sleep(0.1)  # wait for sluggish filesystems
            _unsafe_rmtree(base)
        else:
            os.rmdir(base)


def rmtree(path):
    # type: (str) -> None
    """
    Remove directory tree, with platform-specific fixes.

    Implemented from scratch as :func:`shutil.rmtree` is broken on some
    platforms and python version combinations.

    :param path: path to remove
    """
    error = EnvironmentError
    for retry in range(10):
        try:
            return _unsafe_rmtree(path)
        except EnvironmentError as e:
            if all(getattr(e, p, None) not in v
                   for p, v in RETRYABLE_OSERROR_PROPERTIES.items()):
                raise
            error = e
        time.sleep(0.1)
    raise error


def isexec(path):
    # type: (str) -> bool
    """
    Check if given path points to an executable file.

    :param path: file path
    :return: True if executable, False otherwise
    """
    return os.path.isfile(path) and os.access(path, os.X_OK)


def getdebug(environ=os.environ, true_values=TRUE_VALUES):
    # type: (OSEnvironType, typing.Iterable[str]) -> bool
    """
    Get if app is running in debug mode.

    This is detected looking at environment variables.

    :param environ: environment dict-like object
    :param true_values: iterable of truthy values
    :returns: True if debug contains a true-like string, False otherwise
    """
    return environ.get('DEBUG', '').lower() in true_values


@typing.overload
def deprecated(func_or_text, environ=os.environ):
    # type: (str, OSEnvironType) -> typing.Callable[[TFunction], TFunction]
    """Get deprecation decorator with given message."""


@typing.overload
def deprecated(func_or_text, environ=os.environ):
    # type: (TFunction, OSEnvironType) -> TFunction
    """Decorate with default deprecation message."""


def deprecated(func_or_text, environ=os.environ):
    """
    Decorate function and mark it as deprecated.

    Calling a deprected function will result in a warning message.

    :param func_or_text: message or callable to decorate
    :param environ: optional environment mapping
    :returns: nested decorator or new decorated function (depending on params)

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
    # type: (TFunction) -> typing.Callable[[TFunction2], TFunction2]
    """
    Get decorating function which copies given object __doc__.

    :param other: anything with a __doc__ attribute
    :type other: any
    :returns: decorator function
    :rtype: callable

    Usage:

    .. code-block:: python

        def fnc1():
            '''docstring'''
            pass

        @usedoc(fnc1)
        def fnc2():
            pass

        print(fnc2.__doc__)  # 'docstring'

    """
    def inner(fnc):
        fnc.__doc__ = fnc.__doc__ or getattr(other, '__doc__')
        return fnc
    return inner


def pathsplit(value, sep=os.pathsep):
    # type: (str, str) -> typing.Generator[str, None, None]
    """
    Iterate environment PATH elements.

    This function only cares about spliting across OSes.

    :param value: path string, as given by os.environ['PATH']
    :param sep: PATH separator, defaults to os.pathsep
    :yields: every path
    """
    for part in value.split(sep):
        if part[:1] == part[-1:] == '"' or part[:1] == part[-1:] == '\'':
            part = part[1:-1]
        yield part


def pathparse(value, sep=os.pathsep, os_sep=os.sep):
    # type: (str, str, str) -> typing.Generator[str, None, None]
    """
    Iterate environment PATH directories.

    This function cares about spliting, escapes and normalization of paths
    across OSes.

    :param value: path string, as given by os.environ['PATH']
    :param sep: PATH separator, defaults to os.pathsep
    :param os_sep: OS filesystem path separator, defaults to os.sep
    :yields: every path in PATH
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
        yield normpath(part)


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


def which(name,  # type: str
          env_path=ENV_PATH,  # type: typing.Iterable[str]
          env_path_ext=ENV_PATHEXT,  # type: typing.Iterable[str]
          is_executable_fnc=isexec,  # type: typing.Callable[[str], bool]
          path_join_fnc=os.path.join,  # type: typing.Callable[[...], str]
          os_name=os.name,  # type: str
          ):  # type: (...) -> typing.Optional[str]
    """
    Get command absolute path.

    :param name: name of executable command
    :param env_path: OS environment executable paths, defaults to autodetected
    :param is_executable_fnc: callable will be used to detect if path is
                              executable, defaults to `isexec`
    :param path_join_fnc: callable will be used to join path components
    :param os_name: os name, defaults to os.name
    :return: absolute path
    """
    for path in env_path:
        for suffix in env_path_ext:
            exe_file = path_join_fnc(path, name) + suffix
            if is_executable_fnc(exe_file):
                return exe_file
    return None


def re_escape(pattern, chars=frozenset("()[]{}?*+|^$\\.-#")):
    # type: (str, typing.Iterable[str]) -> str
    """
    Escape pattern to include it safely into another regex.

    This function escapes all special regex characters while translating
    non-ascii characters into unicode escape sequences.

    Logic taken from regex module.

    :param pattern: regex pattern to escape
    :returns: escaped pattern
    """
    chr_escape = '\\{}'.format
    uni_escape = '\\u{:04d}'.format
    return ''.join(
        chr_escape(c) if c in chars or c.isspace() else
        c if '\x19' < c < '\x80' else
        uni_escape(ord(c))
        for c in pattern
        )
