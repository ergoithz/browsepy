#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import os.path
import shutil
import functools

from browsepy.file import Node
from browsepy.compat import map

from .exceptions import InvalidClipboardModeError


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


def paste_clipboard(target, mode, clipboard):
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
    success = []
    issues = []
    mode = 'paste'  # deactivates excluded_clipboard fnc
    for node in map(Node.from_urlpath, clipboard):
        try:
            success.append(paste_fnc(node))
        except BaseException as e:
            issues.append((node, e))
    return success, issues, mode
