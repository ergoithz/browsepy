
import os
import os.path
import tarfile
import threading

import browsepy.compat as compat


class WriteAbort(RuntimeError):
    def __init__(self):
        print('abort')
        super(WriteAbort, self).__init__()


class WritableQueue(object):
    '''
    Minimal threading blocking pipe threading with only `write`, `get` and
    `close` methods.

    This class includes :class:`queue.Queue` specific logic, which itself
    depends on :module:`threading` so any alternate

    Method `write` is exposed instead of `put` for :class:`tarfile.TarFile`
    `fileobj` compatibility.
    '''
    abort_exception = WriteAbort

    def __init__(self):
        self._queue = compat.Queue(maxsize=1)
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
        if self.closed:
            raise self.abort_exception()

        self._queue.put(data)

        if self.closed:
            raise self.abort_exception()

        return len(data)

    def retrieve(self):
        '''
        Get chunk of data from pipe.
        This method blocks if pipe is empty.

        :returns: data chunk
        :rtype: bytes
        :raises WriteAbort: if already closed or closed while blocking
        '''
        if self.closed:
            raise self.abort_exception()

        data = self._queue.get()

        if self.closed and data is None:
            raise self.abort_exception()

        return data

    def close(self):
        '''
        Closes, so any blocked and future writes or retrieves will raise
        :attr:`abort_exception` instances.
        '''
        self.closed = True


class TarFileStream(object):
    '''
    Tarfile which compresses while reading for streaming.

    Buffsize can be provided, it should be 512 multiple (the tar block size)
    for and will be used as tarfile block size.

    Note on corroutines: this class uses threading by default, but
    corroutine-based applications can change this behavior overriding the
    :attr:`event_class` and :attr:`thread_class` values.
    '''

    writable_class = WritableQueue
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
        self._writable = self.writable_class()
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

        tarfile = self.tarfile_class(  # stream write
            fileobj=self._writable,
            mode='w|{}'.format(self._compress),
            bufsize=self._buffsize
            )

        try:
            tarfile.add(self.path, "", filter=infofilter if exclude else None)
            tarfile.close()  # force stream flush
        except self._writable.abort_exception:
            pass
        else:
            self._writable.close()

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
        except self._writable.abort_exception:
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
