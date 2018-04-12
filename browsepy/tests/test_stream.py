
import os
import os.path
import codecs
import unittest
import tempfile
import shutil
import threading

import browsepy.stream


class StreamTest(unittest.TestCase):
    module = browsepy.stream

    def setUp(self):
        self.base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base)

    def randfile(self, size=1024):
        name = codecs.encode(os.urandom(5), 'hex').decode()
        with open(os.path.join(self.base, name), 'wb') as f:
            f.write(os.urandom(size))

    def test_chunks(self):
        self.randfile()
        self.randfile()
        stream = self.module.TarFileStream(self.base, buffsize=5)
        self.assertTrue(next(stream))

        with self.assertRaises(StopIteration):
            while True:
                next(stream)

    def test_close(self):
        self.randfile()
        stream = self.module.TarFileStream(self.base, buffsize=16)
        self.assertTrue(next(stream))
        stream.close()
        with self.assertRaises(StopIteration):
            next(stream)
