"""HTTP utility module."""

import typing
import re

import msgpack

from werkzeug.http import dump_header, dump_options_header, generate_etag
from werkzeug.datastructures import Headers as BaseHeaders


class Headers(BaseHeaders):
    """
    Covenience :class:`werkzeug.datastructures.Headers` wrapper.

    This datastructure allows specifying initial values, as keyword
    arguments while values can be either :type:`str` (no options)
    or tuple of :type:`str` and :type:`dict`.
    """

    snake_replace = staticmethod(re.compile(r'(^|-)[a-z]').sub)

    @classmethod
    def genpair(cls,
                key,  # type: str
                value,  # type: typing.Union[str, typing.Mapping]
                ):  # type: (...) -> typing.Tuple[str, str]
        """
        Fix header name and options to be passed to werkzeug.

        :param key: value key
        :param value: value or value/options pair
        :returns: tuple with key and value
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
        # type: (**typing.Union[str, typing.Mapping]) -> None
        """
        Initialize.

        :param **kwargs: header and values as keyword arguments
        """
        items = [
            self.genpair(key, value)
            for key, value in kwargs.items()
            ]
        return super(Headers, self).__init__(items)


def etag(*args, **kwargs):
    # type: (*typing.Any, **typing.Any) -> str
    """Generate etag identifier from given parameters."""
    return generate_etag(msgpack.dumps((args, kwargs)))
