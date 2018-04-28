#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import string
import json
import base64
import logging
import zlib

from werkzeug.http import dump_header, dump_options_header, dump_cookie, \
                          parse_cookie
from werkzeug.datastructures import Headers as BaseHeaders

from .compat import range, map
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
    NOT_FOUND = object()
    cookie_path = '/'
    page_digits = string.digits + string.ascii_letters
    max_pages = 5
    max_length = 3990
    size_error = InvalidCookieSizeError
    compress_fnc = staticmethod(zlib.compress)
    decompress_fnc = staticmethod(zlib.decompress)
    headers_class = BaseHeaders

    def __init__(self, cookie_name, max_pages=None):
        self.cookie_name = cookie_name
        self.request_cache_field = '_browsepy.cache.cookie.%s' % cookie_name
        self.max_pages = max_pages or self.max_pages

    @classmethod
    def _name_page(cls, page):
        '''
        Converts page integer to string, using fewer characters as possible.
        If string is given, it is returned as is.

        :param page: page number
        :type page: int or str
        :return: page id
        :rtype: str
        '''
        if isinstance(page, str):
            return page

        digits = []

        if page > 1:
            base = len(cls.page_digits)
            remaining = page - 1
            while remaining >= base:
                remaining, modulus = divmod(remaining, base)
                digits.append(modulus)
            digits.append(remaining)
            digits.reverse()

        return ''.join(map(cls.page_digits.__getitem__, digits))

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
        return '{}{}'.format(self.cookie_name, self._name_page(page))

    def _available_cookie_size(self, name):
        '''
        Get available cookie size for value.
        '''
        return self.max_length - len(name + self.cookie_path)

    def _extract_cookies(self, headers):
        '''
        Extract relevant cookies from headers.
        '''
        regex_page_name = '[%s]' % re.escape(self.page_digits)
        regex = re.compile('^%s$' % self._name_cookie_page(regex_page_name))
        return {
            key: value
            for header in headers.get_all('cookie')
            for key, value in parse_cookie(header).items()
            if regex.match(key)
            }

    def load_headers(self, headers):
        '''
        Parse data from relevant paginated cookie data on request headers.

        :param headers: request headers
        :type headers: werkzeug.http.Headers
        :returns: deserialized value
        :rtype: browsepy.abc.JSONSerializable
        '''
        cookies = self._extract_cookies(headers)
        chunks = []
        for i in range(self.max_pages):
            name = self._name_cookie_page(i)
            cookie = cookies.get(name, '').encode('ascii')
            chunks.append(cookie)
            if len(cookie) < self._available_cookie_size(name):
                break
        data = b''.join(chunks)
        try:
            data = base64.b64decode(data)
            serialized = self.decompress_fnc(data)
            return json.loads(serialized.decode('utf-8'))
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

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
        serialized = self.compress_fnc(json.dumps(data).encode('utf-8'))
        data = base64.b64encode(serialized)
        start = 0
        total = len(data)
        for i in range(self.max_pages):
            name = self._name_cookie_page(i)
            end = start + self._available_cookie_size(name)
            result.set(name, data[start:end].decode('ascii'))
            start = end
            if start > total:
                # incidentally, an empty page will be added after start == size
                break
        else:
            # pages exhausted, limit reached
            raise self.size_error(max_cookies=self.max_pages)

        if headers:
            result.extend(self.truncate_headers(headers, i + 1))

        return headers

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
