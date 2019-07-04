# -*- coding: UTF-8 -*-

import os
import errno


class FileActionsException(Exception):
    """
    Base class for file-actions exceptions

    :property path: item path which raised this Exception
    """
    code = None
    template = 'Unhandled error.'

    def __init__(self, message=None, path=None):
        self.path = path
        message = self.template.format(self) if message is None else message
        super(FileActionsException, self).__init__(message)


class InvalidDirnameError(FileActionsException):
    """
    Exception raised when a new directory name is invalid.

    :property path: item path which raised this Exception
    :property name: name which raised this Exception
    """
    code = 'directory-invalid-name'
    template = 'Clipboard item {0.name!r} is not valid.'

    def __init__(self, message=None, path=None, name=None):
        self.name = name
        super(InvalidDirnameError, self).__init__(message, path)


class DirectoryCreationError(FileActionsException):
    """
    Exception raised when a new directory creation fails.

    :property path: item path which raised this Exception
    :property name: name which raised this Exception
    """
    code = 'directory-mkdir-error'
    template = 'Clipboard item {0.name!r} is not valid.'

    def __init__(self, message=None, path=None, name=None):
        self.name = name
        super(DirectoryCreationError, self).__init__(message, path)

    @property
    def message(self):
        return self.args[0]

    @classmethod
    def from_exception(cls, exception, *args, **kwargs):
        message = None
        if isinstance(exception, OSError):
            message = '%s (%s)' % (
                os.strerror(exception.errno),
                errno.errorcode[exception.errno]
                )
        return cls(message, *args, **kwargs)


class ClipboardException(FileActionsException):
    """
    Base class for clipboard exceptions.

    :property path: item path which raised this Exception
    :property mode: mode which raised this Exception
    :property clipboard: :class Clipboard: instance
    """
    code = 'clipboard-invalid'
    template = 'Clipboard is invalid.'

    def __init__(self, message=None, path=None, mode=None, clipboard=None):
        self.mode = mode
        self.clipboard = clipboard
        super(ClipboardException, self).__init__(message, path)


class ItemIssue(tuple):
    """
    Item/error issue
    """
    @property
    def item(self):
        return self[0]

    @property
    def error(self):
        return self[1]

    @property
    def message(self):
        if isinstance(self.error, OSError):
            return '%s (%s)' % (
                os.strerror(self.error.errno),
                errno.errorcode[self.error.errno]
                )

        # ensure full path is never returned
        text = str(self.error)
        text = text.replace(self.item.path, self.item.name)
        return text


class InvalidClipboardItemsError(ClipboardException):
    """
    Exception raised when a clipboard item is not valid.

    :property path: item path which raised this Exception
    :property mode: mode which raised this Exception
    :property clipboard: :class Clipboard: instance
    :property issues: iterable of issues
    """
    pair_class = ItemIssue
    code = 'clipboard-invalid-items'
    template = 'Clipboard has invalid items.'

    def __init__(self, message=None, path=None, mode=None, clipboard=None,
                 issues=()):
        self.issues = list(map(self.pair_class, issues))
        supa = super(InvalidClipboardItemsError, self)
        supa.__init__(message, path, mode, clipboard)

    def append(self, item, error):
        self.issues.append(self.pair_class((item, error)))


class InvalidClipboardModeError(ClipboardException):
    """
    Exception raised when a clipboard mode is not valid.

    :property path: item path which raised this Exception
    :property mode: mode which raised this Exception
    :property clipboard: :class Clipboard: instance
    """
    code = 'clipboard-invalid-mode'
    template = 'Clipboard mode {0.mode!r} is not valid.'

    def __init__(self, message=None, path=None, mode=None, clipboard=None):
        supa = super(InvalidClipboardModeError, self)
        supa.__init__(message, path, mode, clipboard)


class InvalidEmptyClipboardError(ClipboardException):
    """
    Exception raised when an invalid action is requested on an empty clipboard.

    :property path: item path which raised this Exception
    :property mode: mode which raised this Exception
    :property clipboard: :class Clipboard: instance
    """
    code = 'clipboard-invalid-empty'
    template = 'Clipboard action {0.mode!r} cannot be performed without items.'

    def __init__(self, message=None, path=None, mode=None, clipboard=None):
        supa = super(InvalidEmptyClipboardError, self)
        supa.__init__(message, path, mode, clipboard)


class InvalidClipboardSizeError(ClipboardException):
    """
    Exception raised when session manager evicts clipboard data.

    :property path: item path which raised this Exception
    :property mode: mode which raised this Exception
    :property clipboard: :class Clipboard: instance
    """
    code = 'clipboard-invalid-size'
    template = 'Clipboard evicted due session size limit.'

    def __init__(self, message=None, path=None, mode=None, clipboard=None):
        supa = super(InvalidClipboardSizeError, self)
        supa.__init__(message, path, mode, clipboard)
