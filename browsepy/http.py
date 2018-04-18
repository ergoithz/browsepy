
import re

from werkzeug.http import dump_options_header
from werkzeug.datastructures import Headers as BaseHeaders


class Headers(BaseHeaders):
    '''
    A wrapper around :class:`werkzeug.datastructures.Headers`, allowing
    to specify headers with options on initialization.
    '''
    snake_replace = staticmethod(re.compile(r'(^|-)[a-z]').sub)

    @classmethod
    def genpair(cls, key, optkey, values):
        '''
        Extract value and options from values dict based on given key and
        options-key.

        :param key: value key
        :type key: str
        :param optkey: options key
        :type optkey: str
        :param values: value dictionary
        :type values: dict
        :returns: tuple of (key, value)
        :rtype: tuple of str
        '''
        return (
            cls.snake_replace(
                lambda x: x.group(0).upper(),
                key.replace('_', '-')
                ),
            dump_options_header(values[key], values.get(optkey, {})),
            )

    def __init__(self, options_suffix='_options', **kwargs):
        '''
        :param options_suffix: suffix for header options (default: '_options')
        :type options_suffix: str
        :param **kwargs: headers as keyword arguments
        '''
        items = [
            self.genpair(key, '%s%s' % (key, options_suffix), kwargs)
            for key in kwargs
            if not key.endswith(options_suffix)
            ]
        return super(Headers, self).__init__(items)
