#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import unittest
import re
import os
import os.path
import shutil
import tempfile
import tarfile
import xml.etree.ElementTree as ET
import io
import stat

import flask
import browsepy

PY_LEGACY = browsepy.PY_LEGACY

class Page(object):
    @classmethod
    def itertext(cls, element):
        # TODO(ergoithz) on python2 drop: replace by element.itertext()
        yield element.text or ''
        for child in element:
            for text in cls.itertext(child):
                yield text
            yield child.tail or ''

    @classmethod
    def innerText(cls, element):
        return ''.join(cls.itertext(element))


class ListPage(Page):
    path_strip_re = re.compile('\s+/\s+')
    def __init__(self, path, directories, files, removable, upload):
        self.path = path
        self.directories = directories
        self.files = files
        self.removable = removable
        self.upload = upload


    @classmethod
    def from_source(cls, source):
        html = ET.fromstring(source)
        rows = [
            (
                row[0].attrib.get('class') == 'dir-icon',
                row[1].find('.//a').attrib['href'],
                any(button.attrib.get('class') == 'remove button' for button in row[2].findall('.//a'))
            )
            for row in html.findall('.//table/tbody/tr')
        ]
        return cls(
            cls.path_strip_re.sub('/', cls.innerText(html.find('.//h1'))).strip(),
            [url for isdir, url, removable in rows if isdir],
            [url for isdir, url, removable in rows if not isdir],
            all(removable for isdir, url, removable in rows) if rows else False,
            html.find('.//form//input[@type=\'file\']') is not None
        )


class ConfirmPage(Page):
    def __init__(self, path, back):
        self.path = path
        self.back = back

    @classmethod
    def from_source(cls, source):
        html = ET.fromstring(source)

        return cls(
            cls.innerText(html.find('.//form//strong')).strip(),
            html.find('.//form//a').attrib['href']
        )


class PageException(Exception):
    def __init__(self, status):
        self.status = status


class Page404Exception(PageException):
    pass


class TestApp(unittest.TestCase):
    list_page_class = ListPage
    confirm_page_class = ConfirmPage
    page_exceptions = {
        404: Page404Exception,
        None: PageException
    }

    def setUp(self):
        self.app = browsepy.app
        self.base = tempfile.mkdtemp()
        self.start = os.path.join(self.base, 'start')
        self.remove = os.path.join(self.base, 'remove')
        self.upload = os.path.join(self.base, 'upload')

        os.mkdir(self.start)
        os.mkdir(self.remove)
        os.mkdir(self.upload)

        open(os.path.join(self.start, 'testfile.txt'), 'w').close()
        open(os.path.join(self.remove, 'testfile.txt'), 'w').close()

        self.app.config.update(
            directory_base = self.base,
            directory_start = self.start,
            directory_remove = self.remove,
            directory_upload = self.upload,
            SERVER_NAME = 'test',
        )

        self.base_directories = [
            self.url_for('browse', path='remove'),
            self.url_for('browse', path='start'),
            self.url_for('browse', path='upload'),
            ]
        self.start_files = [self.url_for('open', path='start/testfile.txt')]
        self.remove_files = [self.url_for('open', path='remove/testfile.txt')]
        self.upload_files = []

    def clear(self, path):
        assert path.startswith(self.base + os.sep), 'Cannot clear directories out of base'

        for sub in os.listdir(path):
            sub = os.path.join(path, sub)
            if os.path.isdir(sub):
                shutil.rmtree(sub)
            else:
                os.remove(sub)

    def tearDown(self):
        shutil.rmtree(self.base)

    def get(self, endpoint, **kwargs):
        if endpoint in ('index', 'browse'):
            page_class = self.list_page_class
        elif endpoint == 'remove':
            page_class = self.confirm_page_class
        else:
            page_class = None

        with self.app.test_client() as client:
            response = client.get(self.url_for(endpoint, **kwargs))
            if response.status_code != 200:
                raise self.page_exceptions.get(response.status_code, self.page_exceptions[None])(response.status_code)
            return response.data if page_class is None else page_class.from_source(response.data)

    def post(self, endpoint, **kwargs):
        data = kwargs.pop('data') if 'data' in kwargs else {}
        with self.app.test_client() as client:
            response = client.post(self.url_for(endpoint, **kwargs), data=data, follow_redirects=True)
            if response.status_code != 200:
                raise self.page_exceptions.get(response.status_code, self.page_exceptions[None])(response.status_code)
            return self.list_page_class.from_source(response.data)

    def url_for(self, endpoint, **kwargs):
        with self.app.app_context():
            return flask.url_for(endpoint, _external=False, **kwargs)

    def test_index(self):
        page = self.get('index')
        self.assertEqual(page.path, '%s/start' % os.path.basename(self.base))

        self.app.config['directory_start'] = os.path.join(self.base, '..')

        self.assertRaises(
            Page404Exception,
            self.get, 'index'
        )

        self.app.config['directory_start'] = self.start

    def test_browse(self):
        basename = os.path.basename(self.base)
        page = self.get('browse')
        self.assertEqual(page.path, basename)
        self.assertEqual(page.directories, self.base_directories)
        self.assertFalse(page.removable)
        self.assertFalse(page.upload)

        page = self.get('browse', path='start')
        self.assertEqual(page.path, '%s/start' % basename)
        self.assertEqual(page.files, self.start_files)
        self.assertFalse(page.removable)
        self.assertFalse(page.upload)

        page = self.get('browse', path='remove')
        self.assertEqual(page.path, '%s/remove' % basename)
        self.assertEqual(page.files, self.remove_files)
        self.assertTrue(page.removable)
        self.assertFalse(page.upload)

        page = self.get('browse', path='upload')
        self.assertEqual(page.path, '%s/upload' % basename)
        self.assertEqual(page.files, self.upload_files)
        self.assertFalse(page.removable)
        self.assertTrue(page.upload)

        self.assertRaises(
            Page404Exception,
            self.get, 'browse', path='..'
        )

    def test_open(self):
        content = b'hello world'
        with open(os.path.join(self.start, 'testfile3.txt'), 'wb') as f:
            f.write(content)

        data = self.get('open', path='start/testfile3.txt')
        self.assertEqual(data, content)

        self.assertRaises(
            Page404Exception,
            self.get, 'open', path='../shall_not_pass.txt'
        )

    def test_remove(self):
        open(os.path.join(self.remove, 'testfile2.txt'), 'w').close()
        page = self.get('remove', path='remove/testfile2.txt')
        self.assertEqual(page.path, 'remove/testfile2.txt')
        self.assertEqual(page.back, self.url_for('browse', path='remove'))

        basename = os.path.basename(self.base)
        page = self.post('remove', path='remove/testfile2.txt', data={'backurl': self.url_for('browse', path='remove')})
        self.assertEqual(page.path, '%s/remove' % basename)
        self.assertEqual(page.files, self.remove_files)

        os.mkdir(os.path.join(self.remove, 'directory'))
        page = self.post('remove', path='remove/directory', data={'backurl': self.url_for('browse', path='remove')})
        self.assertEqual(page.path, '%s/remove' % basename)
        self.assertEqual(page.files, self.remove_files)

        self.assertRaises(
            Page404Exception,
            self.get, 'remove', path='start/testfile.txt'
        )

        self.assertRaises(
            Page404Exception,
            self.post, 'remove', path='start/testfile.txt', data={'backurl': self.url_for('browse', path='start')}
        )

        self.app.config['directory_remove'] = None

        self.assertRaises(
            Page404Exception,
            self.get, 'remove', path='remove/testfile.txt'
        )

        self.app.config['directory_remove'] = self.remove

        self.assertRaises(
            Page404Exception,
            self.get, 'remove', path='../shall_not_pass.txt'
        )


    def test_download_file(self):
        binfile = os.path.join(self.base, 'testfile.bin')
        bindata = bytes(range(256))

        with open(binfile, 'wb') as f:
            f.write(bindata)
        data = self.get('download_file', path='testfile.bin')
        os.remove(binfile)

        self.assertEqual(data, bindata)

        self.assertRaises(
            Page404Exception,
            self.get, 'download_file', path='../shall_not_pass.txt'
        )

    def test_download_directory(self):
        binfile = os.path.join(self.start, 'testfile.bin')
        bindata = bytes(range(256))

        with open(binfile, 'wb') as f:
            f.write(bindata)
        data = self.get('download_directory', path='start')
        os.remove(binfile)

        iodata = io.BytesIO(data)
        with tarfile.open('start.tgz', mode="r:gz", fileobj=iodata) as tgz:
            tgz_files = [member.name for member in tgz.getmembers() if member.name]
        tgz_files.sort()

        self.assertEqual(tgz_files, ['testfile.bin', 'testfile.txt',])

        self.assertRaises(
            Page404Exception,
            self.get, 'download_directory', path='../../shall_not_pass'
        )

    def test_upload(self):
        c = unichr if PY_LEGACY else chr

        files = {
            'testfile.txt': io.BytesIO(''.join(map(c, range(127))).encode('ascii')),
            'testfile.bin': io.BytesIO(''.join(map(c, range(255))).encode('utf-8')),
        }
        output = self.post('upload',
                           path='upload',
                           data={'file%d' % n: (data, name) for n, (name, data) in enumerate(files.items())}
                           )
        expected_links = sorted(self.url_for('open', path='upload/%s' % i) for i in files)
        self.assertEqual(sorted(output.files), expected_links)
        self.clear(self.upload)


class TestFile(unittest.TestCase):
    def setUp(self):
        self.app = browsepy.app
        self.workbench = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.workbench)

    def testMime(self):
        f = browsepy.File('non_working_path')
        self.assertEqual(f.mimetype, 'application/octet-stream')

        f = browsepy.File('non_working_path_with_ext.txt')
        self.assertEqual(f.mimetype, 'text/plain')


        tmp_txt = os.path.join(self.workbench, 'ascii_text_file')
        with open(tmp_txt, 'w') as f:
            f.write('ascii text')

        # test file command
        f = browsepy.File(tmp_txt)
        self.assertEqual(f.mimetype, 'text/plain; charset=us-ascii')
        self.assertEqual(f.type, 'text/plain')
        self.assertEqual(f.encoding, 'us-ascii')

        # test non-working file command
        bad_path = os.path.join(self.workbench, 'path')
        os.mkdir(bad_path)

        bad_file = os.path.join(bad_path, 'file')
        with open(bad_file, 'w') as f:
            f.write('#!/usr/bin/env bash\nexit 1\n')
        os.chmod(bad_file, os.stat(bad_file).st_mode | stat.S_IEXEC)

        old_path = os.environ['PATH']
        os.environ['PATH'] = bad_path + os.pathsep + old_path

        f = browsepy.File(tmp_txt)
        self.assertEqual(f.mimetype, 'application/octet-stream')

        os.environ['PATH'] = old_path

    def testSize(self):
        test_file = os.path.join(self.workbench, 'test.csv')
        with open(test_file, 'w') as f:
            f.write(',\n'*512)
        f = browsepy.File(test_file)

        default = self.app.config['use_binary_multiples']

        self.app.config['use_binary_multiples'] = True
        self.assertEqual(f.size, '1.00 KiB')

        self.app.config['use_binary_multiples'] = False
        self.assertEqual(f.size, '1.02 KB')

        self.app.config['use_binary_multiples'] = default

        self.assertEqual(f.encoding, 'default')

    def testProperties(self):
        empty_file = os.path.join(self.workbench, 'empty.txt')
        open(empty_file, 'w').close()
        f = browsepy.File(empty_file)

        self.assertEqual(f.basename, 'empty.txt')
        self.assertEqual(f.can_download, True)
        self.assertEqual(f.can_remove, False)
        self.assertEqual(f.can_upload, False)
        self.assertEqual(f.dirname, self.workbench)
        self.assertEqual(f.is_directory, False)


class TestFunctions(unittest.TestCase):
    def test_fmt_size(self):
        fnc = browsepy.fmt_size
        for n, unit in enumerate(browsepy.binary_units):
            self.assertEqual(fnc(2**(10*n)), (1, unit))
        for n, unit in enumerate(browsepy.standard_units):
            self.assertEqual(fnc(1000**n, False), (1, unit))

    def test_empty_iterable(self):
        fnc = browsepy.empty_iterable
        empty, iterable = fnc(i for i in ())
        self.assertTrue(empty)
        self.assertRaises(StopIteration, next, iterable)
        empty, iterable = fnc(i for i in (1, 2))
        self.assertFalse(empty)
        self.assertEqual(tuple(iterable), (1, 2))

    def test_secure_filename(self):
        self.assertEqual(browsepy.secure_filename('/path'), 'path')
        self.assertEqual(browsepy.secure_filename('..'), '')
        self.assertEqual(browsepy.secure_filename('::'), '')
        self.assertEqual(browsepy.secure_filename('\0'), '_')
        self.assertEqual(browsepy.secure_filename('/'), '')
        self.assertEqual(browsepy.secure_filename('C:\\'), '')
        self.assertEqual(browsepy.secure_filename('COM1.asdf', destiny_os='nt'), '')
        self.assertEqual(browsepy.secure_filename('\xf1', fs_encoding='ascii'), '_')

        if PY_LEGACY:
            expected = unicode('\xf1', encoding='latin-1')
            self.assertEqual(browsepy.secure_filename('\xf1', fs_encoding='utf-8'), expected)
            self.assertEqual(browsepy.secure_filename(expected, fs_encoding='utf-8'), expected)
        else:
            self.assertEqual(browsepy.secure_filename('\xf1', fs_encoding='utf-8'), '\xf1')


if __name__ == '__main__':
    unittest.main()
