#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import unittest
import re
import os
import os.path
import shutil
import tempfile
import tarfile
import xml.etree.ElementTree as ET
import io
import mimetypes

import flask

from werkzeug.exceptions import NotFound

import browsepy
import browsepy.file
import browsepy.manager
import browsepy.__main__
import browsepy.compat
import browsepy.tests.utils as test_utils

PY_LEGACY = browsepy.compat.PY_LEGACY
range = browsepy.compat.range  # noqa


class AppMock(object):
    config = browsepy.app.config.copy()


class Page(object):
    @classmethod
    def itertext(cls, element):
        '''
        Compatible element.itertext()
        '''
        if element.text:
            yield element.text
        for child in element:
            for text in cls.itertext(child):
                yield text
            if child.tail:
                yield child.tail

    def __init__(self, data, response=None):
        self.data = data
        self.response = response

    @classmethod
    def innerText(cls, element, sep=''):
        return sep.join(cls.itertext(element))

    @classmethod
    def from_source(cls, source, response=None):
        return cls(source, response)


class ListPage(Page):
    path_strip_re = re.compile('\s+/\s+')

    def __init__(self, path, directories, files, removable, upload, tarfile,
                 source, response=None):
        self.path = path
        self.directories = directories
        self.files = files
        self.removable = removable
        self.upload = upload
        self.tarfile = tarfile
        self.source = source
        self.response = response

    @classmethod
    def from_source(cls, source, response=None):
        html = ET.fromstring(source)
        rows = [
            (
                row[0].attrib.get('class') == 'icon inode',
                row[1].find('.//a').attrib['href'],
                any(button.attrib.get('class') == 'button remove'
                    for button in row[2].findall('.//a')),
                any(button.attrib.get('class') == 'button download'
                    for button in row[2].findall('.//a'))
            )
            for row in html.findall('.//table/tbody/tr')
        ]
        return cls(
            cls.path_strip_re.sub(
                '/',
                cls.innerText(html.find('.//h1'), '/')
                ).strip(),
            [url for isdir, url, removable, download in rows if isdir],
            [url for isdir, url, removable, download in rows if not isdir],
            all(removable
                for isdir, url, removable, download in rows
                ) if rows else False,
            html.find('.//form//input[@type=\'file\']') is not None,
            all(download
                for isdir, url, removable, download in rows if isdir
                ) if rows else False,
            source,
            response
        )


class ConfirmPage(Page):
    def __init__(self, path, name, back, source, response=None):
        self.path = path
        self.name = name
        self.back = back
        self.source = source
        self.response = response

    @classmethod
    def from_source(cls, source, response=None):
        html = ET.fromstring(source)
        name = cls.innerText(html.find('.//strong')).strip()
        prefix = html.find('.//strong').attrib.get('data-prefix', '')

        return cls(
            prefix + name,
            name,
            html.find('.//form[@method=\'get\']').attrib['action'],
            source,
            response
        )


class PageException(Exception):
    def __init__(self, status, *args):
        self.status = status
        super(PageException, self).__init__(status, *args)


class Page404Exception(PageException):
    pass


class Page400Exception(PageException):
    pass


class Page302Exception(PageException):
    pass


class TestApp(unittest.TestCase):
    module = browsepy
    generic_page_class = Page
    list_page_class = ListPage
    confirm_page_class = ConfirmPage
    page_exceptions = {
        404: Page404Exception,
        400: Page400Exception,
        302: Page302Exception,
        None: PageException
    }

    def setUp(self):
        self.app = self.module.app
        self.base = tempfile.mkdtemp()
        self.start = os.path.join(self.base, 'start')
        self.remove = os.path.join(self.base, 'remove')
        self.upload = os.path.join(self.base, 'upload')
        self.exclude = os.path.join(self.base, 'exclude')

        os.mkdir(self.start)
        os.mkdir(self.remove)
        os.mkdir(self.upload)
        os.mkdir(self.exclude)

        open(os.path.join(self.start, 'testfile.txt'), 'w').close()
        open(os.path.join(self.remove, 'testfile.txt'), 'w').close()
        open(os.path.join(self.exclude, 'testfile.txt'), 'w').close()

        def exclude_fnc(path):
            return path == self.exclude \
                or path.startswith(self.exclude + os.sep)

        self.app.config.update(
            directory_base=self.base,
            directory_start=self.start,
            directory_remove=self.remove,
            directory_upload=self.upload,
            exclude_fnc=exclude_fnc,
            SERVER_NAME='test',
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
        assert path.startswith(self.base + os.sep), \
               'Cannot clear directories out of base'

        for sub in os.listdir(path):
            sub = os.path.join(path, sub)
            if os.path.isdir(sub):
                shutil.rmtree(sub)
            else:
                os.remove(sub)

    def tearDown(self):
        shutil.rmtree(self.base)
        test_utils.clear_flask_context()

    def get(self, endpoint, **kwargs):
        status_code = kwargs.pop('status_code', 200)
        follow_redirects = kwargs.pop('follow_redirects', False)
        if endpoint in ('index', 'browse'):
            page_class = self.list_page_class
        elif endpoint == 'remove':
            page_class = self.confirm_page_class
        elif endpoint == 'sort' and follow_redirects:
            page_class = self.list_page_class
        else:
            page_class = self.generic_page_class
        with kwargs.pop('client', None) or self.app.test_client() as client:
            response = client.get(
                self.url_for(endpoint, **kwargs),
                follow_redirects=follow_redirects
                )
            if response.status_code != status_code:
                raise self.page_exceptions.get(
                    response.status_code,
                    self.page_exceptions[None]
                    )(response.status_code)
            result = page_class.from_source(response.data, response)
            response.close()
        test_utils.clear_flask_context()
        return result

    def post(self, endpoint, **kwargs):
        status_code = kwargs.pop('status_code', 200)
        data = kwargs.pop('data') if 'data' in kwargs else {}
        with kwargs.pop('client', None) or self.app.test_client() as client:
            response = client.post(
                self.url_for(endpoint, **kwargs),
                data=data,
                follow_redirects=True
                )
            if response.status_code != status_code:
                raise self.page_exceptions.get(
                    response.status_code,
                    self.page_exceptions[None]
                    )(response.status_code)
            result = self.list_page_class.from_source(response.data, response)
        test_utils.clear_flask_context()
        return result

    def url_for(self, endpoint, **kwargs):
        with self.app.app_context():
            return flask.url_for(endpoint, _external=False, **kwargs)

    def test_index(self):
        page = self.get('index')
        self.assertEqual(page.path, '%s/start' % os.path.basename(self.base))

        start = os.path.abspath(os.path.join(self.base, '..'))
        self.app.config['directory_start'] = start

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

        self.assertRaises(
            Page404Exception,
            self.get, 'browse', path='start/testfile.txt'
        )

        self.assertRaises(
            Page404Exception,
            self.get, 'browse', path='exclude'
        )

        self.app.config['directory_downloadable'] = True
        page = self.get('browse')
        self.assertTrue(page.tarfile)
        self.app.config['directory_downloadable'] = False
        page = self.get('browse')
        self.assertFalse(page.tarfile)

    def test_open(self):
        content = b'hello world'
        with open(os.path.join(self.start, 'testfile3.txt'), 'wb') as f:
            f.write(content)

        page = self.get('open', path='start/testfile3.txt')
        self.assertEqual(page.data, content)

        self.assertRaises(
            Page404Exception,
            self.get, 'open', path='../shall_not_pass.txt'
        )

    def test_remove(self):
        open(os.path.join(self.remove, 'testfile2.txt'), 'w').close()
        page = self.get('remove', path='remove/testfile2.txt')
        self.assertEqual(page.name, 'testfile2.txt')
        self.assertEqual(page.path, 'remove/testfile2.txt')
        self.assertEqual(page.back, self.url_for('browse', path='remove'))

        basename = os.path.basename(self.base)
        page = self.post('remove', path='remove/testfile2.txt')
        self.assertEqual(page.path, '%s/remove' % basename)
        self.assertEqual(page.files, self.remove_files)

        os.mkdir(os.path.join(self.remove, 'directory'))
        page = self.post('remove', path='remove/directory')
        self.assertEqual(page.path, '%s/remove' % basename)
        self.assertEqual(page.files, self.remove_files)

        self.assertRaises(
            Page404Exception,
            self.get, 'remove', path='start/testfile.txt'
        )

        self.assertRaises(
            Page404Exception,
            self.post, 'remove', path='start/testfile.txt'
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

        self.assertRaises(
            Page404Exception,
            self.get, 'remove', path='exclude/testfile.txt'
        )

    def test_download_file(self):
        binfile = os.path.join(self.base, 'testfile.bin')
        bindata = bytes(range(256))

        with open(binfile, 'wb') as f:
            f.write(bindata)
        page = self.get('download_file', path='testfile.bin')
        os.remove(binfile)

        self.assertEqual(page.data, bindata)

        self.assertRaises(
            Page404Exception,
            self.get, 'download_file', path='../shall_not_pass.txt'
        )

        self.assertRaises(
            Page404Exception,
            self.get, 'download_file', path='start'
        )

        self.assertRaises(
            Page404Exception,
            self.get, 'download_file', path='exclude/testfile.txt'
        )

    def test_download_directory(self):
        binfile = os.path.join(self.start, 'testfile.bin')
        excfile = os.path.join(self.start, 'testfile.exc')
        bindata = bytes(range(256))
        exclude = self.app.config['exclude_fnc']

        def tarball_files(path):
            page = self.get('download_directory', path=path)
            iodata = io.BytesIO(page.data)
            with tarfile.open('p.tgz', mode="r:gz", fileobj=iodata) as tgz:
                tgz_files = [
                    member.name
                    for member in tgz.getmembers()
                    if member.name
                    ]
            tgz_files.sort()
            return tgz_files

        for path in (binfile, excfile):
            with open(path, 'wb') as f:
                f.write(bindata)

        self.app.config['exclude_fnc'] = None

        self.assertEqual(
            tarball_files('start'),
            ['testfile.%s' % x for x in ('bin', 'exc', 'txt')]
        )

        self.app.config['exclude_fnc'] = lambda p: p.endswith('.exc')

        self.assertEqual(
            tarball_files('start'),
            ['testfile.%s' % x for x in ('bin', 'txt')]
        )

        self.app.config['exclude_fnc'] = exclude

        self.assertRaises(
            Page404Exception,
            self.get, 'download_directory', path='../../shall_not_pass'
        )

        self.assertRaises(
            Page404Exception,
            self.get, 'download_directory', path='exclude'
        )

    def test_upload(self):
        def genbytesio(nbytes, encoding):
            c = unichr if PY_LEGACY else chr  # noqa
            return io.BytesIO(''.join(map(c, range(nbytes))).encode(encoding))

        files = {
            'testfile.txt': genbytesio(127, 'ascii'),
            'testfile.bin': genbytesio(255, 'utf-8'),
        }
        output = self.post(
            'upload',
            path='upload',
            data={
                'file%d' % n: (data, name)
                for n, (name, data) in enumerate(files.items())
                }
            )
        expected_links = sorted(
            self.url_for('open', path='upload/%s' % i)
            for i in files
            )
        self.assertEqual(sorted(output.files), expected_links)
        self.clear(self.upload)

        self.assertRaises(
            Page404Exception,
            self.post, 'upload', path='start', data={
                'file': (genbytesio(127, 'ascii'), 'testfile.txt')
                }
            )

    def test_upload_duplicate(self):
        c = unichr if PY_LEGACY else chr  # noqa

        files = (
            ('testfile.txt', 'something'),
            ('testfile.txt', 'something_new'),
        )
        output = self.post(
            'upload',
            path='upload',
            data={
               'file%d' % n: (io.BytesIO(data.encode('ascii')), name)
               for n, (name, data) in enumerate(files)
               }
            )

        self.assertEqual(len(files), len(output.files))

        first_file_url = self.url_for('open', path='upload/%s' % files[0][0])
        self.assertIn(first_file_url, output.files)

        file_contents = []
        for filename in os.listdir(self.upload):
            with open(os.path.join(self.upload, filename), 'r') as f:
                file_contents.append(f.read())
        file_contents.sort()

        expected_file_contents = sorted(content for filename, content in files)

        self.assertEqual(file_contents, expected_file_contents)
        self.clear(self.upload)

    def test_upload_restrictions(self):
        pathconf = browsepy.compat.pathconf(self.upload)
        maxname = pathconf['PC_NAME_MAX']
        maxpath = pathconf['PC_PATH_MAX']

        longname = ''.join(('a',) * maxname)

        self.assertRaises(
            Page400Exception,
            self.post, 'upload', path='upload', data={
                'file': (io.BytesIO('test'.encode('ascii')), longname + 'a')
                }
            )

        subdirs = [longname] * (
            (maxpath - len(self.upload) + len(os.sep)) //
            (maxname + len(os.sep))
            )
        longpath = os.path.join(self.upload, *subdirs)

        os.makedirs(longpath)
        self.assertRaises(
            Page400Exception,
            self.post, 'upload', path='upload/' + '/'.join(subdirs), data={
                'file': (io.BytesIO('test'.encode('ascii')), longname)
                }
            )

        self.assertRaises(
            Page400Exception,
            self.post, 'upload', path='upload', data={
                'file': (io.BytesIO('test'.encode('ascii')), '..')
                }
            )

    def test_sort(self):

        self.assertRaises(
            Page404Exception,
            self.get, 'sort', property='text', path='exclude'
        )

        files = {
            'a.txt': 'aaa',
            'b.png': 'aa',
            'c.zip': 'a'
        }
        by_name = [
            self.url_for('open', path=name)
            for name in sorted(files)
            ]
        by_name_desc = list(reversed(by_name))

        by_type = [
            self.url_for('open', path=name)
            for name in sorted(files, key=lambda x: mimetypes.guess_type(x)[0])
            ]
        by_type_desc = list(reversed(by_type))

        by_size = [
            self.url_for('open', path=name)
            for name in sorted(files, key=lambda x: len(files[x]))
            ]
        by_size_desc = list(reversed(by_size))

        for name, content in files.items():
            path = os.path.join(self.base, name)
            with open(path, 'wb') as f:
                f.write(content.encode('ascii'))

        client = self.app.test_client()
        page = self.get('browse', client=client)
        self.assertListEqual(page.files, by_name)

        self.assertRaises(
            Page302Exception,
            self.get, 'sort', property='text', client=client
        )

        page = self.get('browse', client=client)
        self.assertListEqual(page.files, by_name)

        page = self.get('sort', property='-text', client=client,
                        follow_redirects=True)
        self.assertListEqual(page.files, by_name_desc)

        page = self.get('sort', property='type', client=client,
                        follow_redirects=True)
        self.assertListEqual(page.files, by_type)

        page = self.get('sort', property='-type', client=client,
                        follow_redirects=True)
        self.assertListEqual(page.files, by_type_desc)

        page = self.get('sort', property='size', client=client,
                        follow_redirects=True)
        self.assertListEqual(page.files, by_size)

        page = self.get('sort', property='-size', client=client,
                        follow_redirects=True)
        self.assertListEqual(page.files, by_size_desc)

        # We're unable to test modified sorting due filesystem time resolution
        page = self.get('sort', property='modified', client=client,
                        follow_redirects=True)

        page = self.get('sort', property='-modified', client=client,
                        follow_redirects=True)

    def test_sort_cookie_size(self):
        files = [chr(i) * 150 for i in range(97, 123)]
        for name in files:
            path = os.path.join(self.base, name)
            os.mkdir(path)

        client = self.app.test_client()
        for name in files:
            page = self.get('sort', property='modified', path=name,
                            client=client, status_code=302)

            for cookie in page.response.headers.getlist('set-cookie'):
                if cookie.startswith('browse-sorting='):
                    self.assertLessEqual(len(cookie), 4000)

    def test_endpoints(self):
        # test endpoint function for the library use-case
        # likely not to happen when serving due flask's routing protections
        with self.app.app_context():
            self.assertIsInstance(
                self.module.sort(property='name', path='..'),
                NotFound
            )

            self.assertIsInstance(
                self.module.browse(path='..'),
                NotFound
            )

            self.assertIsInstance(
                self.module.open_file(path='../something'),
                NotFound
            )

            self.assertIsInstance(
                self.module.download_file(path='../something'),
                NotFound
            )

            self.assertIsInstance(
                self.module.download_directory(path='..'),
                NotFound
            )

            self.assertIsInstance(
                self.module.remove(path='../something'),
                NotFound
            )

            self.assertIsInstance(
                self.module.upload(path='..'),
                NotFound
            )
