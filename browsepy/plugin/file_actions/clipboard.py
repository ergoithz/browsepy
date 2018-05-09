#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import json
import base64
import logging
import hashlib

from flask import request
from browsepy.http import DataCookie
from browsepy.exceptions import InvalidCookieSizeError

from .exceptions import InvalidClipboardSizeError

logger = logging.getLogger(__name__)


class Clipboard(set):
    '''
    Clipboard (set) with convenience methods to pick its state from request
    cookies and save it to response cookies.
    '''
    data_cookie = DataCookie('clipboard', max_pages=20)
    secret = os.urandom(256)
    request_cache_field = '_browsepy_file_actions_clipboard_cache'

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
            self.__setstate__(cls.data_cookie.load_headers(request.headers))
        except BaseException:
            pass
        return self

    @classmethod
    def _signature(cls, items, mode):
        serialized = json.dumps([items, mode]).encode('utf-8')
        data = cls.secret + serialized
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
        if self:
            data = self.__getstate__()
            try:
                headers = self.data_cookie.dump_headers(data, request.headers)
            except InvalidCookieSizeError as e:
                raise InvalidClipboardSizeError(
                    clipboard=self,
                    max_cookies=e.max_cookies
                    )
        else:
            headers = self.data_cookie.truncate_headers(request.headers)
        response.headers.extend(headers)
