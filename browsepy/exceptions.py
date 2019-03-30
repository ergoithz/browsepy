
class OutsideDirectoryBase(Exception):
    '''
    Exception raised when trying to access to a file outside path defined on
    `directory_base` config property.
    '''
    pass


class OutsideRemovableBase(Exception):
    '''
    Exception raised when trying to access to a file outside path defined on
    `directory_remove` config property.
    '''
    pass


class InvalidPathError(ValueError):
    '''
    Exception raised when a path is not valid.

    :property path: value whose length raised this Exception
    '''
    code = 'invalid-path'
    template = 'Path {0.path!r} is not valid.'

    def __init__(self, message=None, path=None):
        self.path = path
        message = self.template.format(self) if message is None else message
        super(InvalidPathError, self).__init__(message)


class InvalidFilenameError(InvalidPathError):
    '''
    Exception raised when a filename is not valid.

    :property filename: value whose length raised this Exception
    '''
    code = 'invalid-filename'
    template = 'Filename {0.filename!r} is not valid.'

    def __init__(self, message=None, path=None, filename=None):
        self.filename = filename
        super(InvalidFilenameError, self).__init__(message, path=path)


class PathTooLongError(InvalidPathError):
    '''
    Exception raised when maximum filesystem path length is reached.

    :property limit: value length limit
    '''
    code = 'invalid-path-length'
    template = 'Path {0.path!r} is too long, max length is {0.limit}'

    def __init__(self, message=None, path=None, limit=0):
        self.limit = limit
        super(PathTooLongError, self).__init__(message, path=path)


class FilenameTooLongError(InvalidFilenameError):
    '''
    Exception raised when maximum filesystem filename length is reached.
    '''
    code = 'invalid-filename-length'
    template = 'Filename {0.filename!r} is too long, max length is {0.limit}'

    def __init__(self, message=None, path=None, filename=None, limit=0):
        self.limit = limit
        super(FilenameTooLongError, self).__init__(
            message, path=path, filename=filename)
