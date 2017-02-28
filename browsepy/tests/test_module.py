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
import stat
import mimetypes

import flask

from werkzeug.utils import cached_property

import browsepy
import browsepy.file
import browsepy.manager
import browsepy.__main__
import browsepy.compat
import browsepy.tests.utils as test_utils

PY_LEGACY = browsepy.compat.PY_LEGACY
range = browsepy.compat.range  # noqa


class FileMock(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class PluginMock(object):
    registered_arguments_manager = None
    registered_arguments = False
    registered_plugin_manager = None
    registered_plugin = False

    def register_arguments(self, manager):
        self.registered_arguments_manager = manager
        self.registered_arguments = True
        manager.register_argument('--pluginmock', action='store_true')

    def register_plugin(self, manager):
        self.registered_plugin_manager = manager
        self.registered_plugin = True


class AppMock(object):
    config = browsepy.app.config.copy()


class Page(object):
    if hasattr(ET.Element, 'itertext'):
        @classmethod
        def itertext(cls, element):
            return element.itertext()
    else:
        # Old 2.7 minors
        @classmethod
        def itertext(cls, element):
            yield element.text or ''
            for child in element:
                for text in cls.itertext(child):
                    yield text
                yield child.tail or ''

    def __init__(self, data, response=None):
        self.data = data
        self.response = response

    @classmethod
    def innerText(cls, element):
        return ''.join(cls.itertext(element))

    @classmethod
    def from_source(cls, source, response=None):
        return cls(source, response)


class ListPage(Page):
    path_strip_re = re.compile('\s+/\s+')

    def __init__(self, path, directories, files, removable, upload, source,
                 response=None):
        self.path = path
        self.directories = directories
        self.files = files
        self.removable = removable
        self.upload = upload
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
                    for button in row[2].findall('.//a'))
            )
            for row in html.findall('.//table/tbody/tr')
        ]
        return cls(
            cls.path_strip_re.sub(
                '/',
                cls.innerText(html.find('.//h1'))
                ).strip(),
            [url for isdir, url, removable in rows if isdir],
            [url for isdir, url, removable in rows if not isdir],
            all(removable
                for isdir, url, removable in rows
                ) if rows else False,
            html.find('.//form//input[@type=\'file\']') is not None,
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


class Page302Exception(PageException):
    pass


class TestCompat(unittest.TestCase):
    module = browsepy.compat

    def _warn(self, message, category=None, stacklevel=None):
        if not hasattr(self, '_warnings'):
            self._warnings = []
        self._warnings.append({
            'message': message,
            'category': category,
            'stacklevel': stacklevel
            })

    @cached_property
    def assertWarnsRegex(self):
        supa = super(TestCompat, self)
        if hasattr(supa, 'assertWarnsRegex'):
            return supa.assertWarnsRegex
        return self.customAssertWarnsRegex

    def customAssertWarnsRegex(self, expected_warning, expected_regex, fnc,
                               *args, **kwargs):

        import warnings
        old_warn = warnings.warn
        warnings.warn = self._warn
        try:
            fnc(*args, **kwargs)
        finally:
            warnings.warn = old_warn
        warnings = ()
        if hasattr(self, '_warnings'):
            warnings = self._warnings
            del self._warnings
        regex = re.compile(expected_regex)
        self.assertTrue(any(
            warn['category'] == expected_warning and
            regex.match(warn['message'])
            for warn in warnings
        ))

    def test_which(self):
        self.assertTrue(self.module.which('python'))
        self.assertIsNone(self.module.which('lets-put-a-wrong-executable'))

    def test_fsdecode(self):
        path = b'/a/\xc3\xb1'
        self.assertEqual(
            self.module.fsdecode(path, os_name='posix', fs_encoding='utf-8'),
            path.decode('utf-8')
            )
        path = b'/a/\xf1'
        self.assertEqual(
            self.module.fsdecode(path, os_name='nt', fs_encoding='latin-1'),
            path.decode('latin-1')
            )
        path = b'/a/\xf1'
        self.assertRaises(
            UnicodeDecodeError,
            self.module.fsdecode,
            path,
            fs_encoding='utf-8',
            errors='strict'
        )

    def test_fsencode(self):
        path = b'/a/\xc3\xb1'
        self.assertEqual(
            self.module.fsencode(
                path.decode('utf-8'),
                fs_encoding='utf-8'
                ),
            path
            )
        path = b'/a/\xf1'
        self.assertEqual(
            self.module.fsencode(
                path.decode('latin-1'),
                fs_encoding='latin-1'
                ),
            path
            )
        path = b'/a/\xf1'
        self.assertEqual(
            self.module.fsencode(path, fs_encoding='utf-8'),
            path
            )

    def test_getcwd(self):
        self.assertIsInstance(self.module.getcwd(), self.module.unicode)
        self.assertIsInstance(
            self.module.getcwd(
                fs_encoding='latin-1',
                cwd_fnc=lambda: b'\xf1'
                ),
            self.module.unicode
            )
        self.assertIsInstance(
            self.module.getcwd(
                fs_encoding='utf-8',
                cwd_fnc=lambda: b'\xc3\xb1'
                ),
            self.module.unicode
            )

    def test_getdebug(self):
        enabled = ('TRUE', 'true', 'True', '1', 'yes', 'enabled')
        for case in enabled:
            self.assertTrue(self.module.getdebug({'DEBUG': case}))
        disabled = ('FALSE', 'false', 'False', '', '0', 'no', 'disabled')
        for case in disabled:
            self.assertFalse(self.module.getdebug({'DEBUG': case}))

    def test_deprecated(self):
        environ = {'DEBUG': 'true'}
        self.assertWarnsRegex(
            DeprecationWarning,
            'DEPRECATED',
            self.module.deprecated('DEPRECATED', environ)(lambda: None)
            )


class TestApp(unittest.TestCase):
    module = browsepy
    generic_page_class = Page
    list_page_class = ListPage
    confirm_page_class = ConfirmPage
    page_exceptions = {
        404: Page404Exception,
        302: Page302Exception,
        None: PageException
    }

    def setUp(self):
        self.app = self.module.app
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
            directory_base=self.base,
            directory_start=self.start,
            directory_remove=self.remove,
            directory_upload=self.upload,
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

    def test_download_directory(self):
        binfile = os.path.join(self.start, 'testfile.bin')
        bindata = bytes(range(256))

        with open(binfile, 'wb') as f:
            f.write(bindata)
        page = self.get('download_directory', path='start')
        os.remove(binfile)

        iodata = io.BytesIO(page.data)
        with tarfile.open('start.tgz', mode="r:gz", fileobj=iodata) as tgz:
            tgz_files = [
                member.name
                for member in tgz.getmembers()
                if member.name
                ]
        tgz_files.sort()

        self.assertEqual(tgz_files, ['testfile.bin', 'testfile.txt'])

        self.assertRaises(
            Page404Exception,
            self.get, 'download_directory', path='../../shall_not_pass'
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

    def test_sort(self):
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
        files = [chr(i) * 255 for i in range(97, 123)]
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


class TestFile(unittest.TestCase):
    module = browsepy.file

    def setUp(self):
        self.app = browsepy.app  # FIXME
        self.workbench = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.workbench)
        test_utils.clear_flask_context()

    def textfile(self, name, text):
        tmp_txt = os.path.join(self.workbench, name)
        with open(tmp_txt, 'w') as f:
            f.write(text)
        return tmp_txt

    def test_iter_listdir(self):
        directory = self.module.Directory(path=self.workbench, app=self.app)

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

        # test file command
        f = self.module.File(tmp_txt, app=self.app)
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

        f = self.module.File(tmp_txt, app=self.app)
        self.assertEqual(f.mimetype, 'application/octet-stream')

        os.environ['PATH'] = old_path

    def test_size(self):
        test_file = os.path.join(self.workbench, 'test.csv')
        with open(test_file, 'w') as f:
            f.write(',\n' * 512)
        f = self.module.File(test_file, app=self.app)

        default = self.app.config['use_binary_multiples']

        self.app.config['use_binary_multiples'] = True
        self.assertEqual(f.size, '1.00 KiB')

        self.app.config['use_binary_multiples'] = False
        self.assertEqual(f.size, '1.02 KB')

        self.app.config['use_binary_multiples'] = default

        self.assertEqual(f.encoding, 'default')

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
        self.assertEqual(self.module.secure_filename('::'), '')
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
            self.module.relativize_path('/parent/child', '/parent'),
            'child')
        self.assertEqual(
            self.module.relativize_path(
                '/grandpa/parent/child',
                '/grandpa/parent'),
            'child')
        self.assertEqual(
            self.module.relativize_path('/grandpa/parent/child', '/grandpa'),
            'parent/child')
        self.assertRaises(
            browsepy.OutsideDirectoryBase,
            self.module.relativize_path, '/other', '/parent'
        )

    def test_under_base(self):
        self.assertTrue(
            self.module.check_under_base('C:\\as\\df\\gf', 'C:\\as\\df', '\\'))
        self.assertTrue(self.module.check_under_base('/as/df', '/as', '/'))

        self.assertFalse(
            self.module.check_under_base('C:\\cc\\df\\gf', 'C:\\as\\df', '\\'))
        self.assertFalse(self.module.check_under_base('/cc/df', '/as', '/'))


class TestMain(unittest.TestCase):
    module = browsepy.__main__

    def setUp(self):
        self.app = browsepy.app
        self.parser = self.module.ArgParse()
        self.base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_defaults(self):
        result = self.parser.parse_args([])
        self.assertEqual(result.host, '127.0.0.1')
        self.assertEqual(result.port, 8080)
        self.assertEqual(result.directory, os.getcwd())
        self.assertEqual(result.initial, None)
        self.assertEqual(result.removable, None)
        self.assertEqual(result.upload, None)
        self.assertEqual(result.plugin, [])

    def test_params(self):
        plugins = ['plugin_1', 'plugin_2', 'namespace.plugin_3']
        result = self.parser.parse_args([
            '127.1.1.1',
            '5000',
            '--directory=%s' % self.base,
            '--initial=%s' % self.base,
            '--removable=%s' % self.base,
            '--upload=%s' % self.base,
            '--plugin=%s' % ','.join(plugins),
            ])
        self.assertEqual(result.host, '127.1.1.1')
        self.assertEqual(result.port, 5000)
        self.assertEqual(result.directory, self.base)
        self.assertEqual(result.initial, self.base)
        self.assertEqual(result.removable, self.base)
        self.assertEqual(result.upload, self.base)
        self.assertEqual(result.plugin, plugins)

        result = self.parser.parse_args([
            '--directory=%s' % self.base,
            '--initial='
            ])
        self.assertEqual(result.host, '127.0.0.1')
        self.assertEqual(result.port, 8080)
        self.assertEqual(result.directory, self.base)
        self.assertIsNone(result.initial)
        self.assertIsNone(result.removable)
        self.assertIsNone(result.upload)
        self.assertListEqual(result.plugin, [])

        self.assertRaises(
            SystemExit,
            self.parser.parse_args,
            ['--directory=%s' % __file__]
        )

    def test_main(self):
        params = {}
        self.module.main(
            argv=[],
            run_fnc=lambda app, **kwargs: params.update(kwargs)
            )

        defaults = {
            'host': '127.0.0.1',
            'port': 8080,
            'debug': False,
            'threaded': True
            }
        params_subset = {k: v for k, v in params.items() if k in defaults}
        self.assertEqual(defaults, params_subset)


class TestMimetypePluginManager(unittest.TestCase):
    module = browsepy.manager

    def test_mimetype(self):
        manager = self.module.MimetypePluginManager()
        self.assertEqual(
            manager.get_mimetype('potato'),
            'application/octet-stream'
            )
        self.assertEqual(
            manager.get_mimetype('potato.txt'),
            'text/plain'
            )
        manager.register_mimetype_function(
            lambda x: 'application/xml' if x == 'potato' else None
            )
        self.assertEqual(
            manager.get_mimetype('potato.txt'),
            'text/plain'
            )
        self.assertEqual(
            manager.get_mimetype('potato'),
            'application/xml'
            )


class TestPlugins(unittest.TestCase):
    app_module = browsepy
    manager_module = browsepy.manager

    def setUp(self):
        self.app = self.app_module.app
        self.original_namespaces = self.app.config['plugin_namespaces']
        self.plugin_namespace, self.plugin_name = __name__.rsplit('.', 1)
        self.app.config['plugin_namespaces'] = (self.plugin_namespace,)
        self.manager = self.manager_module.PluginManager(self.app)

    def tearDown(self):
        self.app.config['plugin_namespaces'] = self.original_namespaces
        self.manager.clear()
        test_utils.clear_flask_context()

    def test_manager(self):
        self.manager.load_plugin(self.plugin_name)
        self.assertTrue(self.manager._plugin_loaded)

        endpoints = sorted(
            action.endpoint
            for action in self.manager.get_widgets(FileMock(mimetype='a/a'))
            )

        self.assertEqual(
            endpoints,
            sorted(('test_x_x', 'test_a_x', 'test_x_a', 'test_a_a'))
            )
        self.assertEqual(
            self.app.view_functions['test_plugin.root'](),
            'test_plugin_root'
            )
        self.assertIn('test_plugin', self.app.blueprints)

        self.assertRaises(
            self.manager_module.PluginNotFoundError,
            self.manager.load_plugin,
            'non_existent_plugin_module'
            )

        self.assertRaises(
            self.manager_module.InvalidArgumentError,
            self.manager.register_widget
        )

    def test_namespace_prefix(self):
        self.assertTrue(self.manager.import_plugin(self.plugin_name))
        self.app.config['plugin_namespaces'] = (
            self.plugin_namespace + '.test_',
            )
        self.assertTrue(self.manager.import_plugin('module'))


def register_plugin(manager):
    manager._plugin_loaded = True
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_x_x',
        filter=lambda f: True
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_a_x',
        filter=lambda f: f.mimetype.startswith('a/')
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_x_a',
        filter=lambda f: f.mimetype.endswith('/a')
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_a_a',
        filter=lambda f: f.mimetype == 'a/a'
        )
    manager.register_widget(
        type='button',
        place='entry-actions',
        endpoint='test_b_x',
        filter=lambda f: f.mimetype.startswith('b/')
        )

    test_plugin_blueprint = flask.Blueprint(
        'test_plugin',
        __name__,
        url_prefix='/test_plugin_blueprint')
    test_plugin_blueprint.add_url_rule(
        '/',
        endpoint='root',
        view_func=lambda: 'test_plugin_root')

    manager.register_blueprint(test_plugin_blueprint)


if __name__ == '__main__':
    unittest.main()
