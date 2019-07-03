# -*- coding: UTF-8 -*-

import os
import os.path
import tarfile
import threading

import flask

from . import compat


class ByteQueue(compat.Queue):
    '''
    Small synchronized queue storing bytes, with an additional finish method
    with turns the queue :method:`get` into non-blocking (returns empty bytes).

    On a finished queue all :method:`put` will raise Full exceptions,
    regardless of the parameters given.
    '''
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
        '''
        Return the number of bytes in the queue.
        '''
        with self.mutex:
            return self.bytes

    def finish(self):
        '''
        Turn queue into finished mode: :method:`get` becomes non-blocking
        and returning empty bytes if empty, and :method:`put` raising
        :class:`queue.Full` exceptions unconditionally.
        '''
        self.finished = True

        with self.not_full:
            self.not_empty.notify()


class WriteAbort(Exception):
    '''
    Exception used internally by :class:`TarFileStream`'s default
    implementation to stop tarfile compression.
    '''
    pass


class TarFileStream(compat.Iterator):
    '''
    Iterator class which yields tarfile chunks for streaming.

    This class implements :class:`collections.abc.Iterator` interface
    with :method:`close`, so it can be appropriately handled by wsgi servers
    (`PEP 333<https://www.python.org/dev/peps/pep-0333>`_).

    Buffsize can be provided, it should be 512 multiple (the tar block size)
    for and will be used as tarfile block size.

    This class uses :module:`threading` for offloading.
    '''

    queue_class = ByteQueue
    abort_exception = WriteAbort
    thread_class = threading.Thread
    tarfile_class = tarfile.open

    mimetype = 'application/x-tar'
    compresion_modes = {
        None: ('', 'tar'),
        'gzip': ('gz', 'tgz'),
        'bzip2': ('bz2', 'tar.bz2'),
        'xz': ('xz', 'tar.xz'),
        }

    @property
    def name(self):
        '''
        Filename generated from given path and compression method.
        '''
        return '%s.%s' % (os.path.basename(self.path), self._extension)

    @property
    def encoding(self):
        '''
        Mimetype parameters (such as encoding).
        '''
        return self._compress

    def __init__(self, path, buffsize=10240, exclude=None, compress='gzip',
                 compresslevel=1):
        '''
        Initialize thread and class (thread is not started until interated.)
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
        '''
        self.path = path
        self.exclude = exclude
        self.closed = False

        self._started = False
        self._buffsize = buffsize

        self._compress = compress if compress and buffsize > 15 else None
        self._mode, self._extension = self.compresion_modes[self._compress]

        self._queue = self.queue_class(buffsize)
        self._th = self.thread_class(target=self._fill)
        self._th_exc = None

    @property
    def _infofilter(self):
        '''
        TarInfo filtering function based on :attr:`exclude`.
        '''
        path = self.path
        path_join = os.path.join
        exclude = self.exclude

        def infofilter(info):
            '''
            Filter TarInfo objects for TarFile.

            :param info:
            :type info: tarfile.TarInfo
            :return: infofile or None if file must be excluded
            :rtype: tarfile.TarInfo or None
            '''
            return None if exclude(path_join(path, info.name)) else info

        return infofilter if exclude else None

    def _fill(self):
        '''
        Writes data on internal tarfile instance, which writes to current
        object, using :meth:`write`.

        As this method is blocking, it is used inside a thread.

        This method is called automatically, on a thread, on initialization,
        so there is little need to call it manually.
        '''
        try:
            with self.tarfile_class(
              fileobj=self,
              mode='w|{}'.format(self._mode),
              bufsize=self._buffsize,
              encoding='utf-8',
              ) as tarfile:
                tarfile.add(self.path, '', filter=self._infofilter)
        except self.abort_exception:
            pass
        except Exception as e:
            self._th_exc = e
        finally:
            self._queue.finish()

    def __next__(self):
        '''
        Pulls chunk from tarfile (which is processed on its own thread).

        :param want: number bytes to read, defaults to 0 (all available)
        :type want: int
        :returns: tarfile data as bytes
        :rtype: bytes
        '''
        if self.closed:
            raise StopIteration()

        if not self._started:
            self._started = True
            self._th.start()

        data = self._queue.get()
        if not data:
            raise StopIteration()

        return data

    def write(self, data):
        '''
        Put chunk of data into data queue, used on the tarfile thread.

        This method blocks when pipe is already, applying backpressure to
        writers.

        :param data: bytes to write to pipe
        :type data: bytes
        :returns: number of bytes written
        :rtype: int
        :raises WriteAbort: if already closed or closed while blocking
        '''
        if self.closed:
            raise self.abort_exception()

        try:
            self._queue.put(data)
        except compat.Full:
            raise self.abort_exception()

        return len(data)

    def close(self):
        '''
        Closes tarfile pipe and stops further processing.
        '''
        if not self.closed:
            self.closed = True
            self._queue.finish()
            if self._started and self._th.is_alive():
                self._th.join()
            if self._th_exc:
                raise self._th_exc


def stream_template(template_name, **context):
    '''
    Some templates can be huge, this function returns an streaming response,
    sending the content in chunks and preventing from timeout.

    :param template_name: template
    :param **context: parameters for templates.
    :yields: HTML strings
    :rtype: Iterator of str
    '''
    app = context.get('current_app', flask.current_app)
    app.update_template_context(context)
    template = app.jinja_env.get_template(template_name)
    stream = template.generate(context)
    return flask.Response(flask.stream_with_context(stream))
