
import os
import os.path
import codecs
import unittest
import tempfile
import time

import browsepy.compat as compat
import browsepy.stream


class StreamTest(unittest.TestCase):
    module = browsepy.stream

    def setUp(self):
        self.base = tempfile.mkdtemp()

    def tearDown(self):
        compat.rmtree(self.base)

    def randfile(self, size=1024):
        name = codecs.encode(os.urandom(5), 'hex_codec').decode()
        with open(os.path.join(self.base, name), 'wb') as f:
            f.write(os.urandom(size))

    def test_chunks(self):
        self.randfile()
        self.randfile()
        stream = self.module.TarFileStream(self.base, buffsize=5)

        self.assertFalse(stream._queue.qsize())  # not yet compressing
        self.assertEqual(len(next(stream)), 5)

        while not stream._queue.qsize():
            time.sleep(0.1)

        self.assertGreater(stream._queue.qsize(), 4)
        self.assertLess(stream._queue.qsize(), 10)

        with self.assertRaises(StopIteration):
            while True:
                next(stream)

    def test_exception(self):
        class MyException(Exception):
            pass

        class BrokenQueue(self.module.ByteQueue):
            def put(self, data):
                raise MyException()

        stream = self.module.TarFileStream(self.base, buffsize=5)
        stream._queue = BrokenQueue()

        with self.assertRaises(StopIteration):
            next(stream)

        with self.assertRaises(MyException):
            stream.close()

    def test_close(self):
        self.randfile()
        stream = self.module.TarFileStream(self.base, buffsize=16)
        self.assertTrue(next(stream))
        stream.close()
        with self.assertRaises(StopIteration):
            next(stream)
