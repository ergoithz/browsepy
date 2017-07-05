import flask
import flask.config

from .compat import basestring


class Config(flask.config.Config):
    def __init__(self, root, defaults=None):
        if defaults:
            defaults = self.gendict(defaults)
        super(Config, self).__init__(root, defaults)

    @classmethod
    def genkey(cls, k):
        return k.upper() if isinstance(k, basestring) else k

    @classmethod
    def gendict(cls, *args, **kwargs):
        gk = cls.genkey
        return dict((gk(k), v) for k, v in dict(*args, **kwargs).items())

    def __getitem__(self, k):
        return super(Config, self).__getitem__(self.genkey(k))

    def __setitem__(self, k, v):
        super(Config, self).__setitem__(self.genkey(k), v)

    def __delitem__(self, k):
        super(Config, self).__delitem__(self.genkey(k))

    def update(self, *args, **kwargs):
        super(Config, self).update(self.gendict(*args, **kwargs))


class Flask(flask.Flask):
    config_class = Config