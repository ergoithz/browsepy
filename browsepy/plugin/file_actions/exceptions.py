

class FileActionsException(Exception):
    '''
    Base class for file-actions exceptions
    '''
    code = None
    template = 'Unhandled error.'

    def __init__(self, message=None, path=None):
        self.path = path
        message = self.template.format(self) if message is None else message
        super(FileActionsException, self).__init__(message)


class InvalidDirnameError(FileActionsException):
    '''
    Exception raised when a clipboard item is not valid.

    :property name: name which raised this Exception
    '''
    code = 'invalid-dirname'
    template = 'Clipboard item {0.name!r} is not valid.'

    def __init__(self, message=None, path=None, name=None):
        self.name = name
        super(InvalidDirnameError, self).__init__(message, path)


class ClipboardException(FileActionsException):
    '''
    Base class for clipboard exceptions.
    '''
    pass


class InvalidClipboardItemError(ClipboardException):
    '''
    Exception raised when a clipboard item is not valid.

    :property path: item path which raised this Exception
    '''
    code = 'invalid-clipboard-item'
    template = 'Clipboard item {0.item!r} is not valid.'

    def __init__(self, message=None, path=None, item=None):
        self.item = item
        super(InvalidClipboardItemError, self).__init__(message, path)


class MissingClipboardItemError(InvalidClipboardItemError):
    '''
    Exception raised when a clipboard item is not valid.

    :property path: item path which raised this Exception
    '''
    code = 'missing-clipboard-item'
    template = 'Clipboard item {0.item!r} not found.'

    def __init__(self, message=None, path=None, item=None):
        self.item = item
        super(InvalidClipboardItemError, self).__init__(message, path)


class InvalidClipboardModeError(ClipboardException):
    '''
    Exception raised when a clipboard mode is not valid.

    :property mode: mode which raised this Exception
    '''
    code = 'invalid-clipboard-mode'
    template = 'Clipboard mode {0.path!r} is not valid.'

    def __init__(self, message=None, path=None, mode=None):
        self.mode = mode
        super(InvalidClipboardModeError, self).__init__(message, path)


class InvalidClipboardSizeError(ClipboardException):
    '''
    Exception raised when a clipboard size exceeds cookie limit.

    :property max_cookies: maximum allowed size
    '''
    code = 'invalid-clipboard-size'
    template = 'Clipboard has too many items.'

    def __init__(self, message=None, path=None, max_cookies=0):
        self.max_cookies = max_cookies
        super(InvalidClipboardSizeError, self).__init__(message, path)
