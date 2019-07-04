# -*- coding: UTF-8 -*-

import warnings

import flask
import flask.config

from .compat import basestring


class Config(flask.config.Config):
    """
    Flask-compatible case-insensitive Config class.

    See :type:`flask.config.Config` for more info.
    """
    def __init__(self, root, defaults=None):
        self._warned = set()
        if defaults:
            defaults = self.gendict(defaults)
        super(Config, self).__init__(root, defaults)

    def genkey(self, k):
        """
        Key translation function.

        :param k: key
        :type k: str
        :returns: uppercase key
        ;rtype: str
        """
        if isinstance(k, basestring):
            if k not in self._warned and k != k.upper():
                self._warned.add(k)
                warnings.warn(
                    'Config accessed with lowercase key '
                    '%r, lowercase config is deprecated.' % k,
                    DeprecationWarning,
                    3
                    )
            return k.upper()
        return k

    def gendict(self, *args, **kwargs):
        """
        Pre-translated key dictionary constructor.

        See :type:`dict` for more info.

        :returns: dictionary with uppercase keys
        :rtype: dict
        """
        gk = self.genkey
        return dict((gk(k), v) for k, v in dict(*args, **kwargs).items())

    def __getitem__(self, k):
        return super(Config, self).__getitem__(self.genkey(k))

    def __setitem__(self, k, v):
        super(Config, self).__setitem__(self.genkey(k), v)

    def __delitem__(self, k):
        super(Config, self).__delitem__(self.genkey(k))

    def get(self, k, default=None):
        return super(Config, self).get(self.genkey(k), default)

    def pop(self, k, *args):
        return super(Config, self).pop(self.genkey(k), *args)

    def update(self, *args, **kwargs):
        super(Config, self).update(self.gendict(*args, **kwargs))


class Flask(flask.Flask):
    """
    Flask class using case-insensitive :type:`Config` class.

    See :type:`flask.Flask` for more info.
    """
    config_class = Config
