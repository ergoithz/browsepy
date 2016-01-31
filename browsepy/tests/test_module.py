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

import flask
import browsepy
import browsepy.file
import browsepy.manager
import browsepy.widget
import browsepy.__main__
import browsepy.compat

PY_LEGACY = browsepy.compat.PY_LEGACY
range = browsepy.compat.range


class FileMock(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

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
    def __init__(self, path, name, back):
        self.path = path
        self.name = name
        self.back = back

    @classmethod
    def from_source(cls, source):
        html = ET.fromstring(source)
        name = cls.innerText(html.find('.//strong')).strip()
        prefix = html.find('.//strong').attrib.get('data-prefix', '')

        return cls(
            prefix+name,
            name,
            html.find('.//form[@method=\'get\']').attrib['action']
        )


class PageException(Exception):
    def __init__(self, status):
        self.status = status


class Page404Exception(PageException):
    pass


class TestApp(unittest.TestCase):
    module = browsepy
    list_page_class = ListPage
    confirm_page_class = ConfirmPage
    page_exceptions = {
        404: Page404Exception,
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
            result = response.data if page_class is None else page_class.from_source(response.data)
            response.close()
            return result

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

    def test_upload_duplicate(self):
        c = unichr if PY_LEGACY else chr

        files = (
            ('testfile.txt', 'something'),
            ('testfile.txt', 'something_new'),
        )
        output = self.post('upload',
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


class TestFile(unittest.TestCase):
    module = browsepy.file

    def setUp(self):
        self.app = browsepy.app # FIXME
        self.workbench = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.workbench)

    def test_mime(self):
        f = self.module.File('non_working_path')
        self.assertEqual(f.mimetype, 'application/octet-stream')

        f = self.module.File('non_working_path_with_ext.txt')
        self.assertEqual(f.mimetype, 'text/plain')

        tmp_txt = os.path.join(self.workbench, 'ascii_text_file')
        with open(tmp_txt, 'w') as f:
            f.write('ascii text')

        # test file command
        f = self.module.File(tmp_txt)
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

        f = self.module.File(tmp_txt)
        self.assertEqual(f.mimetype, 'application/octet-stream')

        os.environ['PATH'] = old_path

    def test_size(self):
        test_file = os.path.join(self.workbench, 'test.csv')
        with open(test_file, 'w') as f:
            f.write(',\n'*512)
        f = self.module.File(test_file)

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
        f = self.module.File(empty_file)

        self.assertEqual(f.name, 'empty.txt')
        self.assertEqual(f.can_download, True)
        self.assertEqual(f.can_remove, False)
        self.assertEqual(f.can_upload, False)
        self.assertEqual(f.parent.path, self.workbench)
        self.assertEqual(f.is_directory, False)

    def test_choose_filename(self):
        f = self.module.File(self.workbench)
        first_file =  os.path.join(self.workbench, 'testfile.txt')

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
            self.assertEqual(fnc(2**(10*n)), (1, unit))
        for n, unit in enumerate(self.module.standard_units):
            self.assertEqual(fnc(1000**n, False), (1, unit))

    def test_secure_filename(self):
        self.assertEqual(self.module.secure_filename('/path'), 'path')
        self.assertEqual(self.module.secure_filename('..'), '')
        self.assertEqual(self.module.secure_filename('::'), '')
        self.assertEqual(self.module.secure_filename('\0'), '_')
        self.assertEqual(self.module.secure_filename('/'), '')
        self.assertEqual(self.module.secure_filename('C:\\'), '')
        self.assertEqual(self.module.secure_filename('COM1.asdf', destiny_os='nt'), '')
        self.assertEqual(self.module.secure_filename('\xf1', fs_encoding='ascii'), '_')

        if PY_LEGACY:
            expected = unicode('\xf1', encoding='latin-1')
            self.assertEqual(self.module.secure_filename('\xf1', fs_encoding='utf-8'), expected)
            self.assertEqual(self.module.secure_filename(expected, fs_encoding='utf-8'), expected)
        else:
            self.assertEqual(self.module.secure_filename('\xf1', fs_encoding='utf-8'), '\xf1')

    def test_alternative_filename(self):
        self.assertEqual(self.module.alternative_filename('test', 2), 'test (2)')
        self.assertEqual(self.module.alternative_filename('test.txt', 2), 'test (2).txt')
        self.assertEqual(self.module.alternative_filename('test.tar.gz', 2), 'test (2).tar.gz')
        self.assertEqual(self.module.alternative_filename('test.longextension', 2), 'test (2).longextension')
        self.assertEqual(self.module.alternative_filename('test.tar.tar.tar', 2), 'test.tar (2).tar.tar')
        self.assertNotEqual(self.module.alternative_filename('test'), 'test')

    def test_relativize_path(self):
        self.assertEqual(self.module.relativize_path('/parent/child', '/parent'), 'child')
        self.assertEqual(self.module.relativize_path('/grandpa/parent/child', '/grandpa/parent'), 'child')
        self.assertEqual(self.module.relativize_path('/grandpa/parent/child', '/grandpa'), 'parent/child')
        self.assertRaises(
            browsepy.OutsideDirectoryBase,
            self.module.relativize_path, '/other', '/parent'
        )

    def test_under_base(self):
        self.assertTrue(self.module.check_under_base('C:\\as\\df\\gf', 'C:\\as\\df', '\\'))
        self.assertTrue(self.module.check_under_base('/as/df', '/as', '/'))

        self.assertFalse(self.module.check_under_base('C:\\cc\\df\\gf', 'C:\\as\\df', '\\'))
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
        result = self.parser.parse_args(['127.1.1.1', '5000',
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

    def test_main(self):
        params = {}
        self.module.main(argv=[], run_fnc=lambda app, **kwargs: params.update(kwargs))

        defaults = {'host': '127.0.0.1', 'port': 8080, 'debug': False, 'threaded': True}
        params_subset = {k: v for k, v in params.items() if k in defaults}
        self.assertEqual(defaults, params_subset)

class TestPlugins(unittest.TestCase):
    app_module = browsepy
    manager_module = browsepy.manager
    def setUp(self):
        self.app = self.app_module.app
        self.manager = self.manager_module.PluginManager(self.app)
        self.original_namespaces = self.app.config['plugin_namespaces']
        self.plugin_namespace, self.plugin_name = __name__.rsplit('.', 1)
        self.app.config['plugin_namespaces'] = (self.plugin_namespace,)

    def tearDown(self):
        self.app.config['plugin_namespaces'] = self.original_namespaces

    def test_manager(self):
        self.manager.load_plugin(self.plugin_name)
        self.assertTrue(self.manager._plugin_loaded)

        endpoints = sorted(
            action.endpoint
            for action in self.manager.get_actions(FileMock(mimetype='a/a'))
            )

        self.assertEqual(endpoints, sorted(['test_x_x', 'test_a_x', 'test_x_a', 'test_a_a']))
        self.assertEqual(self.app.view_functions['test_plugin.root'](), 'test_plugin_root')
        self.assertIn('test_plugin', self.app.blueprints)

        self.assertRaises(
            self.manager_module.PluginNotFoundError,
            self.manager.load_plugin,
            'non_existent_plugin_module'
            )


def register_plugin(manager):
    widget_class = browsepy.widget.WidgetBase

    manager._plugin_loaded = True
    manager.register_action('test_x_x', widget_class('test_x_x'), ('*/*',))
    manager.register_action('test_a_x', widget_class('test_a_x'), ('a/*',))
    manager.register_action('test_x_a', widget_class('test_x_a'), ('*/a',))
    manager.register_action('test_a_a', widget_class('test_a_a'), ('a/a',))
    manager.register_action('test_b_x', widget_class('test_b_x'), ('b/*',))

    test_plugin_blueprint = flask.Blueprint('test_plugin', __name__, url_prefix = '/test_plugin_blueprint')
    test_plugin_blueprint.add_url_rule('/', endpoint='root', view_func=lambda: 'test_plugin_root')

    manager.register_blueprint(test_plugin_blueprint)


if __name__ == '__main__':
    unittest.main()
