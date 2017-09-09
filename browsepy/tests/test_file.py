
import os
import os.path
import unittest
import tempfile
import shutil
import stat

import browsepy
import browsepy.file
import browsepy.compat
import browsepy.tests.utils as test_utils


PY_LEGACY = browsepy.compat.PY_LEGACY


class TestFile(unittest.TestCase):
    module = browsepy.file

    def setUp(self):
        self.app = browsepy.app  # FIXME
        self.workbench = tempfile.mkdtemp()

    def clear_workbench(self):
        for entry in browsepy.compat.scandir(self.workbench):
            if entry.is_dir():
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)

    def tearDown(self):
        shutil.rmtree(self.workbench)
        test_utils.clear_flask_context()

    def textfile(self, name, text):
        tmp_txt = os.path.join(self.workbench, name)
        with open(tmp_txt, 'w') as f:
            f.write(text)
        return tmp_txt

    def test_iter_listdir(self):
        directory = self.module.Directory(path=self.workbench)

        tmp_txt = self.textfile('somefile.txt', 'a')

        content = list(directory._listdir(precomputed_stats=True))
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0].size, '1 B')
        self.assertEqual(content[0].path, tmp_txt)

        content = list(directory._listdir(precomputed_stats=False))
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0].size, '1 B')
        self.assertEqual(content[0].path, tmp_txt)

    def test_check_forbidden_filename(self):
        cff = self.module.check_forbidden_filename
        self.assertFalse(cff('myfilename', destiny_os='posix'))
        self.assertTrue(cff('.', destiny_os='posix'))
        self.assertTrue(cff('..', destiny_os='posix'))
        self.assertTrue(cff('::', destiny_os='posix'))
        self.assertTrue(cff('/', destiny_os='posix'))
        self.assertTrue(cff('com1', destiny_os='nt'))
        self.assertTrue(cff('LPT2', destiny_os='nt'))
        self.assertTrue(cff('nul', destiny_os='nt'))
        self.assertFalse(cff('com1', destiny_os='posix'))

    def test_secure_filename(self):
        sf = self.module.secure_filename
        self.assertEqual(sf('a/a'), 'a')
        self.assertEqual(sf('//'), '')
        self.assertEqual(sf('c:\\', destiny_os='nt'), '')
        self.assertEqual(sf('c:\\COM1', destiny_os='nt'), '')
        self.assertEqual(sf('COM1', destiny_os='nt'), '')
        self.assertEqual(sf('COM1', destiny_os='posix'), 'COM1')

    def test_mime(self):
        f = self.module.File('non_working_path', app=self.app)
        self.assertEqual(f.mimetype, 'application/octet-stream')

        f = self.module.File('non_working_path_with_ext.txt', app=self.app)
        self.assertEqual(f.mimetype, 'text/plain')

        tmp_txt = self.textfile('ascii_text_file', 'ascii text')
        tmp_err = os.path.join(self.workbench, 'nonexisting_file')

        # test file command
        if browsepy.compat.which('file'):
            f = self.module.File(tmp_txt, app=self.app)
            self.assertEqual(f.mimetype, 'text/plain; charset=us-ascii')
            self.assertEqual(f.type, 'text/plain')
            self.assertEqual(f.encoding, 'us-ascii')

            f = self.module.File(tmp_err, app=self.app)
            self.assertEqual(f.mimetype, 'application/octet-stream')
            self.assertEqual(f.type, 'application/octet-stream')
            self.assertEqual(f.encoding, 'default')

        # test non-working file command
        bad_path = os.path.join(self.workbench, 'path')
        os.mkdir(bad_path)

        bad_file = os.path.join(bad_path, 'file')
        with open(bad_file, 'w') as f:
            f.write('#!/usr/bin/env bash\nexit 1\n')
        os.chmod(bad_file, os.stat(bad_file).st_mode | stat.S_IEXEC)

        old_path = os.environ['PATH']
        os.environ['PATH'] = bad_path

        try:
            f = self.module.File(tmp_txt, app=self.app)
            self.assertEqual(f.mimetype, 'application/octet-stream')
        finally:
            os.environ['PATH'] = old_path

    def test_size(self):
        test_file = os.path.join(self.workbench, 'test.csv')
        with open(test_file, 'wb') as f:
            f.write(b',\n' * 512)
        f = self.module.File(test_file, app=self.app)

        default = self.app.config['use_binary_multiples']

        self.app.config['use_binary_multiples'] = True
        self.assertEqual(f.size, '1.00 KiB')

        self.app.config['use_binary_multiples'] = False
        self.assertEqual(f.size, '1.02 KB')

        self.app.config['use_binary_multiples'] = default

    def test_stats(self):
        virtual_file = os.path.join(self.workbench, 'file.txt')
        f = self.module.File(virtual_file, app=self.app)

        self.assertRaises(
            browsepy.compat.FileNotFoundError,
            lambda: f.stats
            )
        self.assertEqual(f.modified, None)
        self.assertEqual(f.size, None)

        open(virtual_file, 'w').close()
        self.assertNotEqual(f.modified, None)
        self.assertNotEqual(f.size, None)

    def test_cannot_remove(self):
        virtual_file = os.path.join(self.workbench, 'file.txt')
        n = self.module.Node(virtual_file, app=self.app)

        self.assertFalse(n.can_remove)
        self.assertRaises(
            self.module.OutsideRemovableBase,
            n.remove
            )

        f = self.module.File(virtual_file, app=self.app)
        self.assertFalse(f.can_remove)
        self.assertRaises(
            self.module.OutsideRemovableBase,
            f.remove
            )

    def test_properties(self):
        empty_file = os.path.join(self.workbench, 'empty.txt')
        open(empty_file, 'w').close()
        f = self.module.File(empty_file, app=self.app)

        self.assertEqual(f.name, 'empty.txt')
        self.assertEqual(f.can_download, True)
        self.assertEqual(f.can_remove, False)
        self.assertEqual(f.can_upload, False)
        self.assertEqual(f.parent.path, self.workbench)
        self.assertEqual(f.is_directory, False)

        d = self.module.Directory(self.workbench, app=self.app)
        self.assertEqual(d.is_empty, False)

        d = self.module.Directory(self.workbench, app=self.app)
        listdir = d.listdir(reverse=True)  # generate cache
        self.assertNotEqual(listdir, [])
        self.assertIsNotNone(d._listdir_cache)
        self.clear_workbench()  # empty workbench
        self.assertEqual(d.is_empty, False)  # using cache

        d = self.module.Directory(self.workbench, app=self.app)
        self.assertEqual(d.is_empty, True)

    def test_choose_filename(self):
        f = self.module.Directory(self.workbench, app=self.app)
        first_file = os.path.join(self.workbench, 'testfile.txt')

        filename = f.choose_filename('testfile.txt', attempts=0)
        self.assertEqual(filename, 'testfile.txt')

        open(first_file, 'w').close()

        filename = f.choose_filename('testfile.txt', attempts=0)
        self.assertNotEqual(filename, 'testfile (2).txt')

        filename = f.choose_filename('testfile.txt', attempts=2)
        self.assertEqual(filename, 'testfile (2).txt')

        second_file = os.path.join(self.workbench, filename)
        open(second_file, 'w').close()

        filename = f.choose_filename('testfile.txt', attempts=3)
        self.assertEqual(filename, 'testfile (3).txt')

        filename = f.choose_filename('testfile.txt', attempts=2)
        self.assertNotEqual(filename, 'testfile (2).txt')


class TestFileFunctions(unittest.TestCase):
    module = browsepy.file

    def test_fmt_size(self):
        fnc = self.module.fmt_size
        for n, unit in enumerate(self.module.binary_units):
            self.assertEqual(fnc(2**(10 * n)), (1, unit))
        for n, unit in enumerate(self.module.standard_units):
            self.assertEqual(fnc(1000**n, False), (1, unit))

    def test_secure_filename(self):
        self.assertEqual(self.module.secure_filename('/path'), 'path')
        self.assertEqual(self.module.secure_filename('..'), '')
        self.assertEqual(
            self.module.secure_filename('::'),
            '__' if os.name == 'nt' else ''
            )
        self.assertEqual(self.module.secure_filename('\0'), '_')
        self.assertEqual(self.module.secure_filename('/'), '')
        self.assertEqual(self.module.secure_filename('C:\\'), '')
        self.assertEqual(
            self.module.secure_filename('COM1.asdf', destiny_os='nt'),
            '')
        self.assertEqual(
            self.module.secure_filename('\xf1', fs_encoding='ascii'),
            '_')

        if PY_LEGACY:
            expected = unicode('\xf1', encoding='latin-1')  # noqa
            self.assertEqual(
                self.module.secure_filename('\xf1', fs_encoding='utf-8'),
                expected)
            self.assertEqual(
                self.module.secure_filename(expected, fs_encoding='utf-8'),
                expected)
        else:
            self.assertEqual(
                self.module.secure_filename('\xf1', fs_encoding='utf-8'),
                '\xf1')

    def test_alternative_filename(self):
        self.assertEqual(
            self.module.alternative_filename('test', 2),
            'test (2)')
        self.assertEqual(
            self.module.alternative_filename('test.txt', 2),
            'test (2).txt')
        self.assertEqual(
            self.module.alternative_filename('test.tar.gz', 2),
            'test (2).tar.gz')
        self.assertEqual(
            self.module.alternative_filename('test.longextension', 2),
            'test (2).longextension')
        self.assertEqual(
            self.module.alternative_filename('test.tar.tar.tar', 2),
            'test.tar (2).tar.tar')
        self.assertNotEqual(
            self.module.alternative_filename('test'),
            'test')

    def test_relativize_path(self):
        self.assertEqual(
            self.module.relativize_path(
                '/parent/child',
                '/parent',
                '/'),
            'child')
        self.assertEqual(
            self.module.relativize_path(
                '/grandpa/parent/child',
                '/grandpa/parent',
                '/'),
            'child')
        self.assertEqual(
            self.module.relativize_path(
                '/grandpa/parent/child',
                '/grandpa',
                '/'),
            'parent/child')
        self.assertRaises(
            browsepy.OutsideDirectoryBase,
            self.module.relativize_path, '/other', '/parent', '/'
        )

    def test_under_base(self):
        self.assertTrue(
            self.module.check_under_base('C:\\as\\df\\gf', 'C:\\as\\df', '\\'))
        self.assertTrue(self.module.check_under_base('/as/df', '/as', '/'))

        self.assertFalse(
            self.module.check_under_base('C:\\cc\\df\\gf', 'C:\\as\\df', '\\'))
        self.assertFalse(self.module.check_under_base('/cc/df', '/as', '/'))
