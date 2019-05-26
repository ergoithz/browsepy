# -*- coding: UTF-8 -*-

import os
import os.path
import tarfile
import threading
import functools

import flask

from . import compat


class BlockingPipeAbort(RuntimeError):
    '''
    Exception used internally by :class:`BlockingPipe`'s default
    implementation.
    '''
    pass


class BlockingPipe(object):
    '''
    Minimal pipe class with `write`, `retrieve` and `close` blocking methods.

    This class implementation assumes that :attr:`pipe_class` (set as
    class:`queue.Queue` in current implementation) instances has both `put`
    and `get blocking methods.

    Due its blocking implementation, this class uses :module:`threading`.

    This class exposes :method:`write` for :class:`tarfile.TarFile`
    `fileobj` compatibility.
    '''''
    lock_class = threading.Lock
    pipe_class = functools.partial(compat.Queue, maxsize=1)
    abort_exception = BlockingPipeAbort

    def __init__(self):
        self._pipe = self.pipe_class()
        self._wlock = self.lock_class()
        self._rlock = self.lock_class()
        self.closed = False

    def write(self, data):
        '''
        Put chunk of data onto pipe.
        This method blocks if pipe is already full.

        :param data: bytes to write to pipe
        :type data: bytes
        :returns: number of bytes written
        :rtype: int
        :raises WriteAbort: if already closed or closed while blocking
        '''

        with self._wlock:
            if self.closed:
                raise self.abort_exception()
            self._pipe.put(data)
            return len(data)

    def retrieve(self):
        '''
        Get chunk of data from pipe.
        This method blocks if pipe is empty.

        :returns: data chunk
        :rtype: bytes
        :raises WriteAbort: if already closed or closed while blocking
        '''

        with self._rlock:
            if self.closed:
                raise self.abort_exception()
            data = self._pipe.get()
            if data is None:
                raise self.abort_exception()
            return data

    def __del__(self):
        '''
        Call :method:`BlockingPipe.close`.
        '''
        self.close()

    def close(self):
        '''
        Closes, so any blocked and future writes or retrieves will raise
        :attr:`abort_exception` instances.
        '''

        def blocked():
            '''
            NOOP lock release function for non-owned locks.
            '''
            pass

        if not self.closed:
            self.closed = True

            releasing = writing, reading = [
                lock.release if lock.acquire(False) else blocked
                for lock in (self._wlock, self._rlock)
                ]

            if writing is blocked and reading is not blocked:
                self._pipe.get()

            if reading is blocked and writing is not blocked:
                self._pipe.put(None)

            for release in releasing:
                release()


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

    pipe_class = BlockingPipe
    abort_exception = BlockingPipe.abort_exception
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

    def __init__(self, path, buffsize=10240, exclude=None, compress='gzip'):
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
        '''
        self.path = path
        self.exclude = exclude

        self._started = False
        self._buffsize = buffsize

        self._compress = compress if compress and buffsize > 15 else None
        self._mode, self._extension = self.compresion_modes[self._compress]

        self._pipe = self.pipe_class()
        self._th = self.thread_class(target=self._fill)

    def _fill(self):
        '''
        Writes data on internal tarfile instance, which writes to current
        object, using :meth:`write`.

        As this method is blocking, it is used inside a thread.

        This method is called automatically, on a thread, on initialization,
        so there is little need to call it manually.
        '''
        exclude = self.exclude
        path_join = os.path.join
        path = self.path

        def infofilter(info):
            return None if exclude(path_join(path, info.name)) else info

        tarfile = self.tarfile_class(
            fileobj=self._pipe,
            mode='w|{}'.format(self._mode),
            bufsize=self._buffsize
            )

        try:
            tarfile.add(self.path, "", filter=infofilter if exclude else None)
            tarfile.close()  # force stream flush (may raise)
        except self.abort_exception:
            # expected exception when pipe is closed prematurely
            tarfile.close()  # free fd
        finally:
            self.close()

    def __next__(self):
        '''
        Pulls chunk from tarfile (which is processed on its own thread).

        :param want: number bytes to read, defaults to 0 (all available)
        :type want: int
        :returns: tarfile data as bytes
        :rtype: bytes
        '''
        if not self._started:
            self._started = True
            self._th.start()

        try:
            return self._pipe.retrieve()
        except self.abort_exception:
            raise StopIteration()

    def close(self):
        '''
        Closes tarfile pipe and stops further processing.
        '''
        self._pipe.close()

    def __del__(self):
        '''
        Call :method:`TarFileStream.close`.
        '''
        self.close()


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
