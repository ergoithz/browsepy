

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
    Exception raised when a new directory name is invalid.

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

    :property path: item path which raised this Exception
    :property clipboard: :class Clipboard: instance
    '''
    code = 'invalid-clipboard'
    template = 'Clipboard is invalid.'

    def __init__(self, message=None, path=None, clipboard=None):
        self.clipboard = clipboard
        super(ClipboardException, self).__init__(message, path)


class ItemIssue(tuple):
    '''
    Item/error issue
    '''
    @property
    def item(self):
        return self[0]

    @property
    def error(self):
        return self[1]

    @property
    def code(self):
        if isinstance(self.error, OSError):
            return 'oserror-%d' % self.error.errno


class InvalidClipboardItemsError(ClipboardException):
    '''
    Exception raised when a clipboard item is not valid.

    :property path: item path which raised this Exception
    '''
    pair_class = ItemIssue
    code = 'invalid-clipboard-items'
    template = 'Clipboard has invalid items.'

    def __init__(self, message=None, path=None, clipboard=None, issues=()):
        self.issues = list(map(self.pair_class, issues))
        supa = super(InvalidClipboardItemsError, self)
        supa.__init__(message, path, clipboard)

    def append(self, item, error):
        self.issues.append(self.pair_class(item, error))


class InvalidClipboardModeError(ClipboardException):
    '''
    Exception raised when a clipboard mode is not valid.

    :property mode: mode which raised this Exception
    '''
    code = 'invalid-clipboard-mode'
    template = 'Clipboard mode {0.path!r} is not valid.'

    def __init__(self, message=None, path=None, clipboard=None, mode=None):
        self.mode = mode
        supa = super(InvalidClipboardModeError, self)
        supa.__init__(message, path, clipboard)


class InvalidClipboardSizeError(ClipboardException):
    '''
    Exception raised when a clipboard size exceeds cookie limit.

    :property max_cookies: maximum allowed size
    '''
    code = 'invalid-clipboard-size'
    template = 'Clipboard has too many items.'

    def __init__(self, message=None, path=None, clipboard=None, max_cookies=0):
        self.max_cookies = max_cookies
        supa = super(InvalidClipboardSizeError, self)
        supa.__init__(message, path, clipboard)
