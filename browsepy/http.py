# -*- coding: UTF-8 -*-

import re
import logging

from werkzeug.http import dump_header, dump_options_header
from werkzeug.datastructures import Headers as BaseHeaders


logger = logging.getLogger(__name__)


class Headers(BaseHeaders):
    """
    A wrapper around :class:`werkzeug.datastructures.Headers`, allowing
    to specify headers with options on initialization.

    Headers are provided as keyword arguments while values can be either
    :type:`str` (no options) or tuple of :type:`str` and :type:`dict`.
    """
    snake_replace = staticmethod(re.compile(r'(^|-)[a-z]').sub)

    @classmethod
    def genpair(cls, key, value):
        """
        Extract value and options from values dict based on given key and
        options-key.

        :param key: value key
        :type key: str
        :param value: value or value/options pair
        :type value: str or pair of (str, dict)
        :returns: tuple with key and value
        :rtype: tuple of (str, str)
        """
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
        """
        :param **kwargs: header and values as keyword arguments
        :type **kwargs: str or (str, dict)
        """
        items = [
            self.genpair(key, value)
            for key, value in kwargs.items()
            ]
        return super(Headers, self).__init__(items)
