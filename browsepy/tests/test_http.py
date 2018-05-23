
import re
import logging
import unittest

import werkzeug

import browsepy.http

logger = logging.getLogger(__name__)
rct = re.compile(
    r'([^=;]+)(?:=([^;]*))?\s*(?:$|;\s+)'
    )


def parse_set_cookie_option(name, value):
    '''
    Parse Set-Cookie header option (acepting option 'value' as cookie value),
    both name and value.

    Resulting names are compatible as :func:`werkzeug.http.dump_cookie`
    keyword arguments.

    :param name: option name
    :type name: str
    :param value: option value
    :type value: str
    :returns: tuple of parsed name and option, or None if name is unknown
    :rtype: tuple of str or None
    '''
    try:
        if name == 'Max-Age':
            return 'max_age', int(value)
        if name == 'Expires':
            return 'expires', werkzeug.parse_date(value)
        if name in ('value', 'Path', 'Domain', 'SameSite'):
            return name.lower(), value
        if name in ('Secure', 'HttpOnly'):
            return name.lower(), True
    except (AttributeError, ValueError, TypeError):
        pass
    except BaseException as e:
        logger.exception(e)


def parse_set_cookie(header, option_parse_fnc=parse_set_cookie_option):
    '''
    Parse the content of a Set-Type HTTP header.

    Result options are compatible as :func:`werkzeug.http.dump_cookie`
    keyword arguments.

    :param header: Set-Cookie header value
    :type header: str
    :returns: tuple with cookie name and its options
    :rtype: tuple of str and dict
    '''
    pairs = rct.findall(header)
    name, value = pairs[0]
    pairs[0] = ('value', werkzeug.parse_cookie('v=%s' % value).get('v', None))
    return name, dict(filter(None, (option_parse_fnc(*p) for p in pairs)))


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
