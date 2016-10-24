#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import sys
import itertools

PY_LEGACY = sys.version_info < (3, )
ENV_PATH = []  # populated later

try:
    from scandir import scandir, walk
except ImportError:
    if not hasattr(os, 'scandir'):
        raise
    scandir = os.scandir
    walk = os.walk

fs_encoding = sys.getfilesystemencoding()


def isnonstriterable(iterable):
    '''
    Check if given object is a non-str iterable.

    :param iterable: potential iterable object
    :type iterable: object or builtin
    :return: True if given objects is not str but iterable, False otherwise
    :rtype: bool
    '''
    return hasattr(iterable, '__iter__') and not isinstance(iterable, str_base)


def isexec(path):
    '''
    Check if given path points to an executable file.

    :param path: file path
    :type path: str
    :return: True if executable, False otherwise
    :rtype: bool
    '''
    return os.path.isfile(path) and os.access(path, os.X_OK)


def which(name,
          env_path=ENV_PATH,
          is_executable_fnc=isexec,
          path_join_fnc=os.path.join):
    '''
    Get command absolute path.

    :param name: name of executable command
    :type name: str
    :param env_path: OS environment executable paths, defaults to autodetected
    :type env_path: list of str
    :param is_executable_fnc: callable will be used to detect if path is
                              executable, defaults to `isexec`
    :type is_executable_fnc: callable
    :param path_join_fnc: callable will be used to join path components
    :type path_join_fnc: callable
    :return: absolute path
    :rtype: str or None
    '''
    for path in env_path:
        exe_file = path_join_fnc(path, name)
        if is_executable_fnc(exe_file):
            return exe_file
    return None


def fsdecode(path, os_name=os.name, fs_encoding=fs_encoding, errors=None):
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


def fsencode(path, os_name=os.name, fs_encoding=fs_encoding, errors=None):
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


def getcwd(fs_encoding=fs_encoding, cwd_fnc=os.getcwd):
    '''
    Get current work directory's absolute path.
    Like os.getcwd but garanteed to return an unicode-str object.

    :param fs_encoding: filesystem encoding, defaults to autodetected
    :type fs_encoding: str
    :param cwd_fnc: callable used to get the path, defaults to os.getcwd
    :type cwd_fnc: callable
    :return: path
    :rtype: str
    '''
    path = cwd_fnc()
    if isinstance(path, bytes):
        path = fsdecode(path, fs_encoding=fs_encoding)
    return os.path.abspath(path)

ENV_PATH[:] = (
  fsdecode(path.strip('"'))
  for path in os.environ['PATH'].split(os.pathsep)
  )

if PY_LEGACY:
    FileNotFoundError = type('FileNotFoundError', (OSError,), {})
    range = xrange  # noqa
    filter = itertools.ifilter
    str_base = basestring  # noqa
else:
    FileNotFoundError = FileNotFoundError
    range = range
    filter = filter
    str_base = str
