# -*- coding: UTF-8 -*-

import os
import os.path
import tarfile
import threading
import functools

import flask

from . import compat


class ByteQueue(compat.Queue):
    '''
    Small synchronized queue backed with bytearray, with an additional
    finish method with turns the queue into non-blocking.

    Once bytequeue became finished, all :method:`get` calls return empty bytes,
    and :method:`put` calls raise an exception.
    '''
    def _init(self, maxsize):
        self.queue = bytearray()
        self.finished = False

    def _qsize(self):
        return -1 if self.finished and not self.queue else len(self.queue)

    def _put(self, item):
        if self.finished:
            raise RuntimeError('PUT operation on finished byte queue')
        self.queue.extend(item)

    def _get(self):
        num = self.maxsize
        data, self.queue = bytes(self.queue[:num]), bytearray(self.queue[num:])
        return data

    def finish(self):
        if not self.finished:
            with self.not_full:
                self.not_full.notify_all()

            with self.not_empty:
                self.not_empty.notify_all()

            self.finished = True


class BlockingPipe(object):
    '''
    Minimal pipe class with `write` and `read` blocking methods.

    Due its blocking implementation, this class uses :module:`threading`.

    This class exposes :method:`write` for :class:`tarfile.TarFile`
    `fileobj` compatibility.
    '''
    pipe_class = ByteQueue

    def __init__(self, buffsize=None):
        self._pipe = self.pipe_class(buffsize)
        self._raises = None

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
        if self._raises:
            raise self._raises

        self._pipe.put(data, timeout=1)

        return len(data)

    def read(self):
        '''
        Get chunk of data from pipe.
        This method blocks if pipe is empty.

        :returns: data chunk
        :rtype: bytes
        :raises WriteAbort: if already closed or closed while blocking
        '''
        if self._raises:
            raise self._raises
        return self._pipe.get()

    def finish(self):
        '''
        Notify queue that we're finished, so it became non-blocking returning
        empty bytes.
        '''
        self._pipe.finish()

    def abort(self, exception):
        '''
        Make further writes to raise an exception.

        :param exception: exception to raise on write
        :type exception: Exception
        '''
        self._raises = exception
        self.finish()


class StreamError(RuntimeError):
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

    pipe_class = BlockingPipe
    abort_exception = StreamError
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
        self.closed = False

        self._started = False
        self._buffsize = buffsize

        self._compress = compress if compress and buffsize > 15 else None
        self._mode, self._extension = self.compresion_modes[self._compress]

        self._pipe = self.pipe_class(buffsize)
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
            bufsize=self._buffsize,
            encoding='utf-8',
            )
        try:
            tarfile.add(self.path, '', filter=infofilter if exclude else None)
            tarfile.close()  # force stream flush (may raise)
            self._pipe.finish()
        except self.abort_exception:  # probably closed prematurely
            tarfile.close()  # free fd
        except Exception as e:
            self._pipe.abort(e)

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

        data = self._pipe.read()
        if not data:
            raise StopIteration()
        return data

    def close(self):
        '''
        Closes tarfile pipe and stops further processing.
        '''
        if not self.closed:
            self.closed = True
            if self._started:
                self._pipe.abort(self.abort_exception())
                self._th.join()


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
