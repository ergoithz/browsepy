#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import json
import base64
import logging
import zlib

from werkzeug.http import dump_header, dump_options_header, dump_cookie, \
                          parse_cookie, parse_date
from werkzeug.datastructures import Headers as BaseHeaders

from .compat import range
from .exceptions import InvalidCookieSizeError


logger = logging.getLogger(__name__)


class Headers(BaseHeaders):
    '''
    A wrapper around :class:`werkzeug.datastructures.Headers`, allowing
    to specify headers with options on initialization.

    Headers are provided as keyword arguments while values can be either
    :type:`str` (no options) or tuple of :type:`str` and :type:`dict`.
    '''
    snake_replace = staticmethod(re.compile(r'(^|-)[a-z]').sub)

    @classmethod
    def genpair(cls, key, value):
        '''
        Extract value and options from values dict based on given key and
        options-key.

        :param key: value key
        :type key: str
        :param value: value or value/options pair
        :type value: str or pair of (str, dict)
        :returns: tuple with key and value
        :rtype: tuple of (str, str)
        '''
        rkey = cls.snake_replace(
            lambda x: x.group(0).upper(),
            key.replace('_', '-')
            )
        rvalue = (
            dump_header([value])
            if isinstance(value, str) else
            dump_options_header(*value)
            )
        return rkey, rvalue

    def __init__(self, **kwargs):
        '''
        :param **kwargs: header and values as keyword arguments
        :type **kwargs: str or (str, dict)
        '''
        items = [
            self.genpair(key, value)
            for key, value in kwargs.items()
            ]
        return super(Headers, self).__init__(items)


class DataCookie(object):
    '''
    Compressed base64 paginated cookie manager.

    Usage
    -----

    > from flask import Flask, request, make_response
    >
    > app = Flask(__name__)
    > cookie = DataCookie('my-cookie')
    >
    > @app.route('/get')
    > def get():
    >     return 'Cookie value is %s' % cookie.load(request.cookies)
    >
    > @app.route('/set')
    > def set():
    >     response = make_response('Cookie set')
    >     cookie.dump('setted', response, request.cookies)
    >     return response

    '''
    page_length = 4000
    size_error = InvalidCookieSizeError
    headers_class = BaseHeaders

    @staticmethod
    def _serialize(data):
        '''
        :type data: json-serializable
        :rtype: bytes
        '''
        serialized = zlib.compress(json.dumps(data).encode('utf-8'))
        return base64.b64encode(serialized).decode('ascii')

    @staticmethod
    def _deserialize(data):
        '''
        :type data: bytes
        :rtype: json-serializable
        '''
        decoded = base64.b64decode(data)
        serialized = zlib.decompress(decoded)
        return json.loads(serialized)

    def __init__(self, cookie_name, max_pages=1, max_age=None, path='/'):
        '''
        :param cookie_name: first cookie name and prefix for the following
        :type cookie_name: str
        :param max_pages: maximum allowed cookie parts, defaults to 1
        :type max_pages: int
        :param max_age: cookie lifetime in seconds or None (session, default)
        :type max_age: int, datetime.timedelta or None
        :param path: cookie path, defaults to /
        :type path: str
        '''
        self.cookie_name = cookie_name
        self.max_pages = max_pages
        self.max_age = max_age
        self.path = path

    def _name_cookie_page(self, page):
        '''
        Get name of cookie corresponding to given page.

        By design (see :method:`_name_page`), pages lower than 1 results on
        cookie names without a page name.

        :param page: page number or name
        :type page: int or str
        :returns: cookie name
        :rtype: str
        '''
        return '{}{}'.format(
            self.cookie_name,
            page if isinstance(page, str) else
            '-{:x}'.format(page - 1) if page else
            ''
            )

    def _available_cookie_size(self, name):
        '''
        Get available cookie size for value.

        :param name: cookie name
        :type name: str
        :return: available bytes for cookie value
        :rtype: int
        '''
        empty = 'Set-Cookie: %s' % dump_cookie(
            name,
            value=' ',  # force quotes
            max_age=self.max_age,
            path=self.path
            )
        return self.page_length - len(empty)

    def _extract_cookies(self, headers):
        '''
        Extract relevant cookies from headers.
        '''
        regex = re.compile('^%s$' % self._name_cookie_page('(-[0-9a-f])?'))
        return {
            key: value
            for header in headers.get_all('cookie')
            for key, value in parse_cookie(header).items()
            if regex.match(key)
            }

    def load_cookies(self, cookies, default=None):
        '''
        Parse data from relevant paginated cookie data given as mapping.

        :param cookies: request cookies
        :type cookies: collections.abc.Mapping
        :returns: deserialized value
        :rtype: browsepy.abc.JSONSerializable
        '''
        chunks = []
        for i in range(self.max_pages):
            name = self._name_cookie_page(i)
            cookie = cookies.get(name, '').encode('ascii')
            chunks.append(cookie)
            if len(cookie) < self._available_cookie_size(name):
                break
        data = b''.join(chunks)
        if data:
            try:
                return self._deserialize(data)
            except BaseException:
                pass
        return default

    def load_headers(self, headers, default=None):
        '''
        Parse data from relevant paginated cookie data on request headers.

        :param headers: request headers
        :type headers: werkzeug.http.Headers
        :returns: deserialized value
        :rtype: browsepy.abc.JSONSerializable
        '''
        cookies = self._extract_cookies(headers)
        return self.load_cookies(cookies)

    def dump_headers(self, data, headers=None):
        '''
        Serialize given object into a :class:`werkzeug.datastructures.Headers`
        instance.

        :param data: any json-serializable value
        :type data: browsepy.abc.JSONSerializable
        :param headers: optional request headers, used to truncate old pages
        :type headers: werkzeug.http.Headers
        :return: response headers
        :rtype: werkzeug.http.Headers
        '''
        result = self.headers_class()
        data = self._serialize(data)
        start = 0
        size = len(data)
        for i in range(self.max_pages):
            name = self._name_cookie_page(i)
            end = start + self._available_cookie_size(name)
            result.add(
                'Set-Cookie',
                dump_cookie(
                    name,
                    data[start:end],
                    max_age=self.max_age,
                    path=self.path,
                    )
                )
            if end > size:
                # incidentally, an empty page will be added after end == size
                if headers:
                    result.extend(self.truncate_headers(headers, i + 1))
                return result
            start = end
        # pages exhausted, limit reached
        raise self.size_error(max_cookies=self.max_pages)

    def truncate_headers(self, headers, start=0):
        '''
        Evict relevant cookies found on request headers, optionally starting
        from a given page number.

        :param headers: request headers, required to truncate old pages
        :type headers: werkzeug.http.Headers
        :param start: paginated cookie start, defaults to 0
        :type start: int
        :return: response headers
        :rtype: werkzeug.http.Headers
        '''
        name_cookie = self._name_cookie_page
        cookie_names = set(self._extract_cookies(headers))
        cookie_names.difference_update(name_cookie(i) for i in range(start))

        result = self.headers_class()
        for name in cookie_names:
            result.add('Set-Cookie', dump_cookie(name, expires=0))
        return result


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
            return 'expires', parse_date(value)
        if name in ('value', 'Path', 'Domain', 'SameSite'):
            return name.lower(), value
        if name in ('Secure', 'HttpOnly'):
            return name.lower(), True
    except (AttributeError, ValueError, TypeError):
        pass
    except BaseException as e:
        logger.exception(e)


re_parse_set_cookie = re.compile(r'([^=;]+)(?:=([^;]*))?(?:$|;\s*)')


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
    pairs = re_parse_set_cookie.findall(header)
    name, value = pairs[0]
    pairs[0] = ('value', parse_cookie('v=%s' % value).get('v', None))
    return name, dict(filter(None, (option_parse_fnc(*p) for p in pairs)))
