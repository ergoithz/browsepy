# -*- coding: UTF-8 -*-

import os
import os.path
import shutil
import functools

from browsepy.file import Node, secure_filename
from browsepy.compat import map

from .exceptions import InvalidClipboardModeError, \
                        InvalidEmptyClipboardError,\
                        InvalidDirnameError, \
                        DirectoryCreationError


def copy(target, node, join_fnc=os.path.join):
    if node.is_excluded:
        raise OSError(2, os.strerror(2))

    dest = join_fnc(
        target.path,
        target.choose_filename(node.name)
        )

    if node.is_directory:
        shutil.copytree(node.path, dest)
    else:
        shutil.copy2(node.path, dest)

    return dest


def move(target, node, join_fnc=os.path.join):
    if node.is_excluded or not node.can_remove:
        code = 2 if node.is_excluded else 1
        raise OSError(code, os.strerror(code))
    if node.parent.path != target.path:
        dest = join_fnc(
            target.path,
            target.choose_filename(node.name)
            )
        shutil.move(node.path, dest)
        return dest
    return node.path


def paste(target, mode, clipboard):
    '''
    Get pasting function for given directory and keyboard.
    '''
    if mode == 'cut':
        paste_fnc = functools.partial(move, target)
    elif mode == 'copy':
        paste_fnc = functools.partial(copy, target)
    else:
        raise InvalidClipboardModeError(
            path=target.path,
            mode=mode,
            clipboard=clipboard,
            )

    if not clipboard:
        raise InvalidEmptyClipboardError(
            path=target.path,
            mode=mode,
            clipboard=clipboard,
            )

    success = []
    issues = []
    for node in map(Node.from_urlpath, clipboard):
        try:
            success.append(paste_fnc(node))
        except BaseException as e:
            issues.append((node, e))
    return success, issues


def mkdir(path, name):
    if secure_filename(name) != name or not name:
        raise InvalidDirnameError(path=path, name=name)

    try:
        os.mkdir(os.path.join(path, name))
    except BaseException as e:
        raise DirectoryCreationError.from_exception(e, path=path, name=name)
