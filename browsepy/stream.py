
import os
import os.path
import tarfile
import threading
import functools

import browsepy.compat as compat


class BlockingPipeAbort(RuntimeError):
    '''
    Exception used internally be default's :class:`BlockingPipe`
    implementation.
    '''
    pass

class BlockingPipe(object):
    '''
    Minimal pipe class with `write`, `retrieve` and `close` blocking methods.

    This class implementation assumes that :attr:`pipe_class` (set as
    class:`queue.Queue` in current implementation) instances has both `put`
    and `get blocking methods.

    Due its blocking implementation, this class is only compatible with
    python's threading module, any other approach (like coroutines) will
    require to adapt this class (via inheritance or implementation).

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

    def close(self):
        '''
        Closes, so any blocked and future writes or retrieves will raise
        :attr:`abort_exception` instances.
        '''
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


class TarFileStream(object):
    '''
    Tarfile which compresses while reading for streaming.

    Buffsize can be provided, it should be 512 multiple (the tar block size)
    for and will be used as tarfile block size.

    Note on corroutines: this class uses threading by default, but
    corroutine-based applications can change this behavior overriding the
    :attr:`event_class` and :attr:`thread_class` values.
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
        Compression will start a thread, and will be pausing until consumed.

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
        self._writable = self.pipe_class()
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
            fileobj=self._writable,
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
            return self._writable.retrieve()
        except self.abort_exception:
            raise StopIteration()

    def __iter__(self):
        '''
        This class itself implements iterable protocol, so iter() returns
        this instance itself.

        :returns: instance itself
        :rtype: TarFileStream
        '''
        return self

    def close(self):
        '''
        Finish processing aborting any pending write.
        '''
        self._writable.close()
