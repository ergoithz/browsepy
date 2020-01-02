"""Common browsepy exceptions."""


class OutsideDirectoryBase(Exception):
    """
    Access denied because path outside DIRECTORY_BASE.

    Exception raised when trying to access to a file outside path defined on
    `DIRECTORY_BASE` config property.
    """


class OutsideRemovableBase(Exception):
    """
    Access denied because path outside DIRECTORY_REMOVE.

    Exception raised when trying to access to a file outside path defined on
    `DIRECTORY_REMOVE` config property.
    """


class InvalidPathError(ValueError):
    """Invalid path error, raised when a path is invalid."""

    code = 'invalid-path'
    template = 'Path {0.path!r} is not valid.'

    def __init__(self, message=None, path=None):
        """
        Initialize.

        :param message: custom error message
        :param path: path causing this exception
        """
        self.path = path
        message = self.template.format(self) if message is None else message
        super(InvalidPathError, self).__init__(message)


class InvalidFilenameError(InvalidPathError):
    """Invalid filename error, raised when a provided filename is invalid."""

    code = 'invalid-filename'
    template = 'Filename {0.filename!r} is not valid.'

    def __init__(self, message=None, path=None, filename=None):
        """
        Initialize.

        :param message: custom error message
        :param path: target path
        :param filename: filemane causing this exception
        """
        self.filename = filename
        super(InvalidFilenameError, self).__init__(message, path=path)


class PathTooLongError(InvalidPathError):
    """Path too long for filesystem error."""

    code = 'invalid-path-length'
    template = 'Path {0.path!r} is too long, max length is {0.limit}'

    def __init__(self, message=None, path=None, limit=0):
        """
        Initialize.

        :param message: custom error message
        :param path: path causing this exception
        :param limit: known path length limit
        """
        self.limit = limit
        super(PathTooLongError, self).__init__(message, path=path)


class FilenameTooLongError(InvalidFilenameError):
    """Filename too long for filesystem error."""

    code = 'invalid-filename-length'
    template = 'Filename {0.filename!r} is too long, max length is {0.limit}'

    def __init__(self, message=None, path=None, filename=None, limit=0):
        """
        Initialize.

        :param message: custom error message
        :param path: target path
        :param filename: filename causing this exception
        :param limit: known filename length limit
        """
        self.limit = limit
        super(FilenameTooLongError, self).__init__(
            message, path=path, filename=filename)


class PluginNotFoundError(ImportError):
    """Plugin not found error."""


class WidgetException(Exception):
    """Base widget exception."""


class WidgetParameterException(WidgetException):
    """Invalid widget parameter exception."""


class InvalidArgumentError(ValueError):
    """Invalid manager register_widget argument exception."""
