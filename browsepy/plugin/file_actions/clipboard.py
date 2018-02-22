#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import json
import base64
import logging
import hashlib
import functools

try:
    import lzma
    LZMA_OPTIONS = {
        'format': lzma.FORMAT_RAW,
        'filters': [
            {'id': lzma.FILTER_DELTA, 'dist': 5},
            {'id': lzma.FILTER_LZMA2, 'preset': lzma.PRESET_DEFAULT},
            ]
        }
    compress = functools.partial(lzma.compress, **LZMA_OPTIONS)
    decompress = functools.partial(lzma.decompress, **LZMA_OPTIONS)
except ImportError:
    from zlib import compress, decompress


from flask import request
from browsepy.compat import range

from .exceptions import InvalidClipboardSizeError

logger = logging.getLogger(__name__)


class Clipboard(set):
    '''
    Clipboard (set) with convenience methods to pick its state from request
    cookies and save it to response cookies.
    '''
    cookie_secret = os.urandom(256)
    cookie_name = 'clipboard-{:x}'
    cookie_path = '/'
    request_cache_field = '_browsepy_file_actions_clipboard_cache'
    max_pages = 20

    @classmethod
    def count(cls, request=request):
        '''
        Get how many clipboard items are stores on request cookies.

        :param request: optional request, defaults to current flask request
        :type request: werkzeug.Request
        :return: number of clipboard items on request's cookies
        :rtype: int
        '''
        return len(cls.from_request(request))

    @classmethod
    def from_request(cls, request=request):
        '''
        Create clipboard object from request cookies.
        Uses request itself for cache.

        :param request: optional request, defaults to current flask request
        :type request: werkzeug.Request
        :returns: clipboard instance
        :rtype: Clipboard
        '''
        cached = getattr(request, cls.request_cache_field, None)
        if cached is not None:
            return cached
        self = cls()
        setattr(request, cls.request_cache_field, self)
        try:
            self.__setstate__(cls._read_paginated_cookie(request))
        except BaseException:
            pass
        return self

    @classmethod
    def _paginated_cookie_length(cls, page=0):
        name_fnc = cls.cookie_name.format
        return 3990 - len(name_fnc(page) + cls.cookie_path)

    @classmethod
    def _read_paginated_cookie(cls, request=request):
        chunks = []
        if request:
            name_fnc = cls.cookie_name.format
            for i in range(cls.max_pages):  # 2 ** 32 - 1
                cookie = request.cookies.get(name_fnc(i), '').encode('ascii')
                chunks.append(cookie)
                if len(cookie) < cls._paginated_cookie_length(i):
                    break
        serialized = decompress(base64.b64decode(b''.join(chunks)))
        return json.loads(serialized.decode('utf-8'))

    @classmethod
    def _write_paginated_cookie(cls, data, response):
        serialized = compress(json.dumps(data).encode('utf-8'))
        data = base64.b64encode(serialized)
        name_fnc = cls.cookie_name.format
        start = 0
        size = len(data)
        for i in range(cls.max_pages):
            end = cls._paginated_cookie_length(i)
            response.set_cookie(name_fnc(i), data[start:end].decode('ascii'))
            start = end
            if start > size:  # we need an empty page after start == size
                return i
        raise InvalidClipboardSizeError(max_cookies=cls.max_pages)

    @classmethod
    def _delete_paginated_cookie(cls, response, start=0, request=request):
        name_fnc = cls.cookie_name.format
        for i in range(start, cls.max_pages):
            name = name_fnc(i)
            if name not in request.cookies:
                break
            response.set_cookie(name, '', expires=0)

    @classmethod
    def _signature(cls, items, method):
        serialized = json.dumps(items).encode('utf-8')
        data = cls.cookie_secret + method.encode('utf-8') + serialized
        return base64.b64encode(hashlib.sha512(data).digest()).decode('ascii')

    def __init__(self, iterable=(), mode='copy'):
        self.mode = mode
        super(Clipboard, self).__init__(iterable)

    def __getstate__(self):
        items = list(self)
        return {
            'mode': self.mode,
            'items': items,
            'signature': self._signature(items, self.mode),
            }

    def __setstate__(self, data):
        if data['signature'] == self._signature(data['items'], data['mode']):
            self.update(data['items'])
            self.mode = data['mode']

    def to_response(self, response, request=request):
        '''
        Save clipboard state to response taking care of disposing old clipboard
        cookies from request.

        :param response: response object to write cookies on
        :type response: werkzeug.Response
        :param request: optional request, defaults to current flask request
        :type request: werkzeug.Request
        '''
        start = 0
        if self:
            data = self.__getstate__()
            start = self._write_paginated_cookie(data, response) + 1
        self._delete_paginated_cookie(response, start, request)
