
import re
import unittest
import datetime

import werkzeug

import browsepy.http

resc = re.compile(r'^((?P<key>[^=;]+)(=(?P<value>[^;]+))?(;|$))')

def parse_set_cookies(headers, dt=None):
    '''
    :param headers: header structure
    :type headers: werkzeug.http.Headers
    '''
    if dt is None:
        dt = datetime.datetime.now()
    cookies = {}
    for value in headers.get_all('Set-Cookie'):
        items = [match.groupdict() for match in resc.finditer(value)]
        name = items[0]['key']
        options = {
            item['key'].strip(): item['value'].strip()
            for item in item
            }
        if 'expires' in options:
            options['expires'] = werkzeug.parse_date(options['expires'])




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


class TestDataCookie(unittest.TestCase):
    pass
