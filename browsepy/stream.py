"""Streaming functionality with generators and response constructors."""

import os
import os.path
import tarfile
import threading

import flask

from . import compat


class ByteQueue(compat.Queue):
    """
    Synchronized byte queue, with an additional finish method.

    On a finished, :method:`put` will raise queue.Full exceptions and
    :method:`get` will return empty bytes without blockng.
    """

    def _init(self, maxsize):
        self.queue = []
        self.bytes = 0
        self.finished = False
        self.closed = False

    def _qsize(self):
        return -1 if self.finished else self.bytes

    def _put(self, item):
        if self.finished:
            raise compat.Full
        self.queue.append(item)
        self.bytes += len(item)

    def _get(self):
        size = self.maxsize
        data = b''.join(self.queue)
        data, tail = data[:size], data[size:]
        self.queue[:] = (tail,)
        self.bytes = len(tail)
        return data

    def qsize(self):
        """Return the number of bytes in the queue."""
        with self.mutex:
            return self.bytes

    def finish(self):
        """
        Put queue into finished mode.

        On finished mode, :method:`get` becomes non-blocking once empty
        by returning empty and :method:`put` raises :class:`queue.Full`
        exceptions unconditionally.
        """
        self.finished = True

        with self.not_full:
            self.not_empty.notify()


class WriteAbort(Exception):
    """Exception to stop tarfile compression process."""

    pass


class TarFileStream(compat.Iterator):
    """
    Iterator class which yields tarfile chunks for streaming.

    This class implements :class:`collections.abc.Iterator` interface
    with :method:`close`, so it can be appropriately handled by wsgi servers
    (`PEP 333<https://www.python.org/dev/peps/pep-0333>`_).

    Buffsize can be provided, it should be 512 multiple (the tar block size)
    for and will be used as tarfile block size.

    This class uses :module:`threading` for offloading, so if your exclude
    function would not have access to any thread-local specific data.

    If your exclude function requires accessing to :data:`flask.app`,
    :data:`flask.g`, :data:`flask.request` or any other flask contexts,
    ensure is wrapped with :func:`flask.copy_current_request_context`
    """

    queue_class = ByteQueue
    abort_exception = WriteAbort
    thread_class = threading.Thread
    tarfile_open = tarfile.open
    tarfile_format = tarfile.PAX_FORMAT

    mimetype = 'application/x-tar'
    compresion_modes = {
        None: ('', 'tar'),
        'gzip': ('gz', 'tgz'),
        'bzip2': ('bz2', 'tar.bz2'),
        'xz': ('xz', 'tar.xz'),
        }

    @property
    def name(self):
        """Get filename generated from given path and compression method."""
        return '%s.%s' % (os.path.basename(self.path), self._extension)

    @property
    def encoding(self):
        """Mimetype parameters (such as encoding)."""
        return self._compress

    @property
    def closed(self):
        """Get if input stream have been closed with no further writes."""
        return self._closed

    def __init__(self, path, buffsize=10240, exclude=None, compress='gzip',
                 compresslevel=1):
        """
        Initialize thread and class (thread is not started until iteration).

        Note that compress parameter will be ignored if buffsize is below 16.

        :param path: local path of directory whose content will be compressed.
        :type path: str
        :param buffsize: byte size of tarfile blocks, defaults to 10KiB
        :type buffsize: int
        :param exclude: absolute path filtering function, defaults to None
        :type exclude: callable
        :param compress: compression method ('gz', 'bz2', 'xz' or None)
        :type compress: str or None
        :param compresslevel: compression level [1-9] defaults to 1 (fastest)
        :type compresslevel: int
        """
        self.path = path
        self.exclude = exclude

        self._started = False
        self._closed = False
        self._buffsize = buffsize

        self._compress = compress if compress and buffsize > 15 else None
        self._mode, self._extension = self.compresion_modes[self._compress]

        self._queue = self.queue_class(buffsize)
        self._thread = self.thread_class(target=self._fill)
        self._thread_exception = None

    def _fill(self):
        """
        Compress files in path, pushing compressed data into internal queue.

        Used as compression thread target, started on first iteration.
        """
        path = self.path
        path_join = os.path.join
        exclude = self.exclude

        def infofilter(info):
            """
            Filter TarInfo objects from TarFile.

            :param info:
            :type info: tarfile.TarInfo
            :return: infofile or None if file must be excluded
            :rtype: tarfile.TarInfo or None
            """
            return (
                None
                if exclude(
                    path_join(path, info.name),
                    follow_symlinks=info.issym(),
                    ) else
                info
                )

        try:
            with self.tarfile_open(
              fileobj=self,
              mode='w|{}'.format(self._mode),
              bufsize=self._buffsize,
              format=self.tarfile_format,
              encoding='utf-8',
              ) as tarfile:
                tarfile.add(
                    path,
                    arcname='',  # as archive root
                    recursive=True,
                    filter=infofilter if exclude else None,
                    )
        except self.abort_exception:
            pass
        except Exception as e:
            self._thread_exception = e
        finally:
            self._queue.finish()

    def __next__(self):
        """
        Get chunk from internal queue.

        Starts compression thread on first call.

        :param want: number bytes to read, defaults to 0 (all available)
        :type want: int
        :returns: tarfile data as bytes
        :rtype: bytes
        """
        if self._closed:
            raise StopIteration

        if not self._started:
            self._started = True
            self._thread.start()

        data = self._queue.get()
        if not data:
            raise StopIteration

        return data

    def write(self, data):
        """
        Add chunk of data into data queue.

        This method is used inside the compression thread, blocking when
        the internal queue is already full, propagating backpressure to
        writer.

        :param data: bytes to write to pipe
        :type data: bytes
        :returns: number of bytes written
        :rtype: int
        :raises WriteAbort: if already closed or closed while blocking
        """
        if self._closed:
            raise self.abort_exception()

        try:
            self._queue.put(data)
        except compat.Full:
            raise self.abort_exception()

        return len(data)

    def close(self):
        """Close tarfile pipe and stops further processing."""
        if not self._closed:
            self._closed = True
            self._queue.finish()
            if self._started and self._thread.is_alive():
                self._thread.join()
            if self._thread_exception:
                raise self._thread_exception


def tarfile_extension(compress, tarfile_class=TarFileStream):
    """
    Get file extension for given compression mode (as in contructor).

    :param compress: compression mode
    :returns: file extension
    """
    _, extension = tarfile_class.compresion_modes[compress]
    return extension


def stream_template(template_name, **context):
    """
    Get streaming response rendering a jinja template.

    Some templates can be huge, this function returns an streaming response,
    sending the content in chunks and preventing from timeout.

    :param template_name: template
    :param **context: parameters for templates.
    :yields: HTML strings
    :rtype: Iterator of str
    """
    app = context.get('current_app', flask.current_app)
    app.update_template_context(context)
    template = app.jinja_env.get_template(template_name)
    stream = template.generate(context)
    return app.response_class(flask.stream_with_context(stream))
