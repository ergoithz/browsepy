
import os
import os.path
import tarfile
import threading
import functools

import browsepy.compat as compat


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
        if not self.closed:
            self.closed = True

            # release locks
            reading = not self._rlock.acquire(blocking=False)
            writing = not self._wlock.acquire(blocking=False)

            if not reading:
                if writing:
                    self._pipe.get()
                self._rlock.release()

            if not writing:
                if reading:
                    self._pipe.put(None)
                self._wlock.release()


class TarFileStream(compat.Generator):
    '''
    Iterable/generator class which yields tarfile chunks for streaming.

    This class implements :class:`collections.abc.Generator` interface
    (`PEP 325 <https://www.python.org/dev/peps/pep-0342/>`_),
    so it can be appropriately handled by wsgi servers
    (`PEP 333<https://www.python.org/dev/peps/pep-0333>`_).

    Buffsize can be provided, it should be 512 multiple (the tar block size)
    for and will be used as tarfile block size.

    This class uses :module:`threading` for offloading.
    '''

    pipe_class = BlockingPipe
    abort_exception = BlockingPipe.abort_exception
    thread_class = threading.Thread
    tarfile_class = tarfile.open

    extensions = {
        'gz': 'tgz',
        'bz2': 'tar.bz2',
        'xz': 'tar.xz',
        }

    @property
    def name(self):
        return '%s.%s' % (
            os.path.basename(self.path),
            self.extensions.get(self._compress, 'tar')
            )

    def __init__(self, path, buffsize=10240, exclude=None, compress='gz'):
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
        self._compress = compress if compress and buffsize > 15 else ''
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
            mode='w|{}'.format(self._compress),
            bufsize=self._buffsize
            )

        try:
            tarfile.add(self.path, "", filter=infofilter if exclude else None)
            tarfile.close()  # force stream flush
        except self.abort_exception:
            # expected exception when pipe is closed prematurely
            tarfile.close()  # free fd
        else:
            self.close()

    def send(self, value):
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

    def throw(self, typ, val=None, tb=None):
        '''
        Raise an exception in the coroutine.
        Return next yielded value or raise StopIteration.
        '''
        try:
            if val is None:
                if tb is None:
                    raise typ
                val = typ()
            if tb is not None:
                val = val.with_traceback(tb)
            raise val
        except GeneratorExit:
            self._pipe.close()
            raise

    def __del__(self):
        '''
        Call :method:`TarFileStream.close`,
        '''
        self.close()
