
import os
import unittest
import datetime
import base64
import zlib

import werkzeug.http
import werkzeug.datastructures

import browsepy.http
import browsepy.exceptions


class TestHeaders(unittest.TestCase):
    module = browsepy.http

    def test_simple(self):
        headers = self.module.Headers(
            simple_header='something',
            other_header='something else',
            )
        self.assertEqual(
            headers.get('Simple-Header'),
            'something',
            )

    def test_options(self):
        headers = self.module.Headers(
            option_header=('something', {'option': 1}),
            other_header='something else',
            )
        self.assertEqual(
            headers.get('Option-Header'),
            'something; option=1',
            )


class TestParseSetCookie(unittest.TestCase):
    module = browsepy.http

    def test_parse(self):
        tests = {
            'value-cookie=value': {
                'name': 'value-cookie',
                'value': 'value',
                },
            'expiration-cookie=value; Expires=Thu, 24 May 2018 18:10:26 GMT': {
                'name': 'expiration-cookie',
                'value': 'value',
                'expires': datetime.datetime(2018, 5, 24, 18, 10, 26),
                },
            'maxage-cookie="value with spaces"; Max-Age=0': {
                'name': 'maxage-cookie',
                'value': 'value with spaces',
                'max_age': 0,
                },
            'secret-cookie; HttpOnly; Secure': {
                'name': 'secret-cookie',
                'value': '',
                'httponly': True,
                'secure': True,
                },
            'spaced name=value': {
                'name': 'spaced name',
                'value': 'value',
                },
            }
        for cookie, data in tests.items():
            name, parsed = self.module.parse_set_cookie(cookie)
            parsed['name'] = name
            self.assertEquals(parsed, data)


class TestDataCookie(unittest.TestCase):
    module = browsepy.http
    manager_cls = module.DataCookie
    header_cls = werkzeug.datastructures.Headers
    cookie_size_exception = browsepy.exceptions.InvalidCookieSizeError

    def random_text(self, size=2):
        bytedata = zlib.compress(os.urandom(size * 3), 9)  # ensure entropy
        b64data = base64.b64encode(bytedata)
        return b64data.decode('ascii')[:size]

    def parse_response_cookies(self, headers):
        '''
        :type headers: werkzeug.datastructures.Headers
        '''
        return {
            name: options
            for name, options in map(
                self.module.parse_set_cookie,
                headers.get_all('set-cookie')
                )}

    def response_to_request_headers(self, headers):
        '''
        :type headers: werkzeug.datastructures.Headers
        '''
        return self.header_cls(
            ('Cookie', werkzeug.http.dump_cookie(name, options['value']))
            for name, options in self.parse_response_cookies(headers).items()
            )

    def test_pagination(self):
        data = self.random_text(self.manager_cls.header_max_size)
        manager = self.manager_cls('cookie', max_pages=2)

        rheaders = manager.dump_headers(data)
        self.assertEqual(len(rheaders), 2)

        qheaders = self.response_to_request_headers(rheaders)
        self.assertEqual(manager.load_headers(qheaders), data)

        rheaders = manager.dump_headers('shorter-data', qheaders)
        self.assertEqual(len(rheaders), 2)  # 1 for value, 1 for discard

        cookies = self.parse_response_cookies(rheaders)

        cookie1 = cookies['cookie']
        deserialized = manager.load_cookies({'cookie': cookie1['value']})
        self.assertEqual(deserialized, 'shorter-data')

        cookie2 = cookies['cookie-2']
        self.assertEqual(cookie2['value'], '')
        self.assertLess(cookie2['expires'], datetime.datetime.now())
        self.assertLess(cookie2['max_age'], 1)

    def test_max_pagination(self):
        manager = self.manager_cls('cookie', max_pages=2)
        self.assertRaises(
            self.cookie_size_exception,
            manager.dump_headers,
            self.random_text(self.manager_cls.header_max_size * 2)
            )

    def test_truncate(self):
        qheaders = self.header_cls([('Cookie', 'cookie=value')])
        manager = self.manager_cls('cookie', max_pages=2)
        rheaders = manager.truncate_headers(qheaders)
        parsed = self.parse_response_cookies(rheaders)
        self.assertEqual(parsed['cookie']['value'], '')

    def test_corrupted(self):
        manager = self.manager_cls('cookie')
        default = object()
        data = manager.load_cookies({'cookie': 'corrupted'}, default)
        self.assertIs(data, default)
