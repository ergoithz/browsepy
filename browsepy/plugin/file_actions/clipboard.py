#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import json
import base64
import logging
import hashlib

from flask import request
from browsepy.compat import range


logger = logging.getLogger(__name__)


class Clipboard(set):
    cookie_secret = os.urandom(256)
    cookie_sign_name = 'clipboard-signature'
    cookie_mode_name = 'clipboard-mode'
    cookie_list_name = 'clipboard-{:x}'
    cookie_path = '/'
    request_cache_field = '_browsepy_file_actions_clipboard_cache'
    max_pages = 0xffffffff

    @classmethod
    def count(cls, request=request):
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
        signature = cls._cookiebytes(cls.cookie_sign_name, request)
        data = cls._read_paginated_cookie(request)
        mode = cls._cookietext(cls.cookie_mode_name, request)
        if cls._signature(data, mode) == signature:
            try:
                self.update(json.loads(base64.b64decode(data).decode('utf-8')))
                self.mode = mode
            except:
                pass
        return self

    @classmethod
    def _cookiebytes(cls, name, request=request):
        return request.cookies.get(name, '').encode('ascii')

    @classmethod
    def _cookietext(cls, name, request=request):
        return request.cookies.get(name, '')

    @classmethod
    def _paginated_cookie_length(cls, page=0):
        name_fnc = cls.cookie_list_name.format
        return 3990 - len(name_fnc(page) + cls.cookie_path)

    @classmethod
    def _read_paginated_cookie(cls, request=request):
        chunks = []
        if request:
            name_fnc = cls.cookie_list_name.format
            for i in range(cls.max_pages):  # 2 ** 32 - 1
                cookie = request.cookies.get(name_fnc(i), '').encode('ascii')
                chunks.append(cookie)
                if len(cookie) < cls._paginated_cookie_length(i):
                    break
        return b''.join(chunks)

    @classmethod
    def _write_paginated_cookie(cls, data, response):
        name_fnc = cls.cookie_list_name.format
        start = 0
        size = len(data)
        for i in range(cls.max_pages):
            end = cls._paginated_cookie_length(i)
            response.set_cookie(name_fnc(i), data[start:end].decode('ascii'))
            start = end
            if start > size:  # we need an empty page after start == size
                return i
        return 0

    @classmethod
    def _delete_paginated_cookie(cls, response, start=0, request=request):
        name_fnc = cls.cookie_list_name.format
        for i in range(start, cls.max_pages):
            name = name_fnc(i)
            if name not in request.cookies:
                break
            response.set_cookie(name, '', expires=0)

    @classmethod
    def _signature(cls, data, method):
        data = cls.cookie_secret + method.encode('utf-8') + data
        return base64.b64encode(hashlib.sha512(data).digest())

    def __init__(self, iterable=(), mode='copy'):
        self.mode = mode
        super(Clipboard, self).__init__(iterable)

    def to_response(self, response, request=request):
        if self:
            data = base64.b64encode(json.dumps(list(self)).encode('utf-8'))
            signature = self._signature(data, self.mode)
            start = self._write_paginated_cookie(data, response) + 1
            response.set_cookie(self.cookie_mode_name, self.mode)
            response.set_cookie(self.cookie_sign_name, signature)
        else:
            start = 0
            response.set_cookie(self.cookie_mode_name, '', expires=0)
            response.set_cookie(self.cookie_sign_name, '', expires=0)
        self._delete_paginated_cookie(response, start, request)
