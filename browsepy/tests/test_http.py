
import os
import unittest
import datetime
import base64

import browsepy.http


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

    def random_text(self, size=2):
        bytedata = base64.b64encode(os.urandom(size))
        return bytedata.decode('ascii')[:size]

    def test_pagination(self):
        data = self.random_text(self.manager_cls.page_length)
        manager = self.manager_cls('cookie', max_pages=3)
        headers = manager.dump_headers(data)
        print(headers)
        self.assertEqual(len(headers), 2)
        self.assertEqual(manager.load_headers(headers), data)

