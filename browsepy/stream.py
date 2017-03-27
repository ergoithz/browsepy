
import os
import os.path
import tarfile
import functools
import threading


class TarFileStream(object):
    '''
    Tarfile which compresses while reading for streaming.

    Buffsize can be provided, it must be 512 multiple (the tar block size) for
    compression.

    Note on corroutines: this class uses threading by default, but
    corroutine-based applications can change this behavior overriding the
    :attr:`event_class` and :attr:`thread_class` values.
    '''
    event_class = threading.Event
    thread_class = threading.Thread
    tarfile_class = tarfile.open

    def __init__(self, path, buffsize=10240, exclude=None):
        '''
        Internal tarfile object will be created, and compression will start
        on a thread until buffer became full with writes becoming locked until
        a read occurs.

        :param path: local path of directory whose content will be compressed.
        :type path: str
        :param buffsize: size of internal buffer on bytes, defaults to 10KiB
        :type buffsize: int
        :param exclude: path filter function, defaults to None
        :type exclude: callable
        '''
        self.path = path
        self.name = os.path.basename(path) + ".tgz"
        self.exclude = exclude

        self._finished = 0
        self._want = 0
        self._data = bytes()
        self._add = self.event_class()
        self._result = self.event_class()
        self._tarfile = self.tarfile_class(  # stream write
            fileobj=self,
            mode="w|gz",
            bufsize=buffsize
            )
        self._th = self.thread_class(target=self.fill)
        self._th.start()

    def fill(self):
        '''
        Writes data on internal tarfile instance, which writes to current
        object, using :meth:`write`.

        As this method is blocking, it is used inside a thread.

        This method is called automatically, on a thread, on initialization,
        so there is little need to call it manually.
        '''
        if self.exclude:
            exclude = self.exclude
            ap = functools.partial(os.path.join, self.path)
            self._tarfile.add(
                self.path, "",
                filter=lambda info: None if exclude(ap(info.name)) else info
                )
        else:
            self._tarfile.add(self.path, "")
        self._tarfile.close()  # force stream flush
        self._finished += 1
        if not self._result.is_set():
            self._result.set()

    def write(self, data):
        '''
        Write method used by internal tarfile instance to output data.
        This method blocks tarfile execution once internal buffer is full.

        As this method is blocking, it is used inside the same thread of
        :meth:`fill`.

        :param data: bytes to write to internal buffer
        :type data: bytes
        :returns: number of bytes written
        :rtype: int
        '''
        self._add.wait()
        self._data += data
        if len(self._data) > self._want:
            self._add.clear()
            self._result.set()
        return len(data)

    def read(self, want=0):
        '''
        Read method, gets data from internal buffer while releasing
        :meth:`write` locks when needed.

        The lock usage means it must ran on a different thread than
        :meth:`fill`, ie. the main thread, otherwise will deadlock.

        The combination of both write and this method running on different
        threads makes tarfile being streamed on-the-fly, with data chunks being
        processed and retrieved on demand.

        :param want: number bytes to read, defaults to 0 (all available)
        :type want: int
        :returns: tarfile data as bytes
        :rtype: bytes
        '''
        if self._finished:
            if self._finished == 1:
                self._finished += 1
                return ""
            return EOFError("EOF reached")

        # Thread communication
        self._want = want
        self._add.set()
        self._result.wait()
        self._result.clear()

        if want:
            data = self._data[:want]
            self._data = self._data[want:]
        else:
            data = self._data
            self._data = bytes()
        return data

    def __iter__(self):
        '''
        Iterate through tarfile result chunks.

        Similarly to :meth:`read`, this methos must ran on a different thread
        than :meth:`write` calls.

        :yields: data chunks as taken from :meth:`read`.
        :ytype: bytes
        '''
        data = self.read()
        while data:
            yield data
            data = self.read()
