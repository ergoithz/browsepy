"""Flask app config utilities."""

import typing
import warnings

import flask
import flask.config

from . import compat


T = typing.TypeVar('T')


class Config(flask.config.Config):
    """
    Flask-compatible case-insensitive Config class.

    See :type:`flask.config.Config` for more info.
    """

    def __init__(self, root, defaults=None):
        """Initialize."""
        self._warned = set()
        if defaults:
            defaults = self.gendict(defaults)
        super(Config, self).__init__(root, defaults)

    def genkey(self, key):  # type: (T) -> T
        """
        Get translated key.

        :param k: key
        :returns: uppercase key
        """
        if isinstance(key, str):
            uppercase = key.upper()
            if key not in self._warned and key != uppercase:
                self._warned.add(key)
                warnings.warn(
                    'Config accessed with lowercase key '
                    '%r, lowercase config is deprecated.' % key,
                    DeprecationWarning,
                    3
                    )
            return uppercase
        return key

    def gendict(self, *args, **kwargs):  # type: (...) -> dict
        """
        Generate dictionary with pre-translated keys.

        See :type:`dict` for more info.

        :returns: dictionary with uppercase keys
        """
        gk = self.genkey
        return dict((gk(k), v) for k, v in dict(*args, **kwargs).items())

    def __getitem__(self, k):
        """Return self[k]."""
        return super(Config, self).__getitem__(self.genkey(k))

    def __setitem__(self, k, v):
        """Assign value to key, same as self[k]=value."""
        super(Config, self).__setitem__(self.genkey(k), v)

    def __delitem__(self, k):
        """Remove item, same as del self[k]."""
        super(Config, self).__delitem__(self.genkey(k))

    def get(self, k, default=None):
        """Get option from config, return default if not found."""
        return super(Config, self).get(self.genkey(k), default)

    def pop(self, k, *args):
        """Remove and get option from config, accepts an optional default."""
        return super(Config, self).pop(self.genkey(k), *args)

    def update(self, *args, **kwargs):
        """Update current object with given keys and values."""
        super(Config, self).update(self.gendict(*args, **kwargs))


class Flask(flask.Flask):
    """
    Flask class using case-insensitive :type:`Config` class.

    See :type:`flask.Flask` for more info.
    """

    config_class = Config


class AppDecoratorProxy(object):
    """Flask app decorator proxy."""

    def __init__(self, name, nested=False):
        """Initialize."""
        self.name = name
        self.nested = nested

    def __get__(self, obj, type=None):
        """Get deferred registering decorator."""
        def decorator(*args, **kwargs):
            def wrapper(fnc):
                def callback():
                    meth = getattr(flask.current_app, self.name)
                    meth(*args, **kwargs)(fnc) if self.nested else meth(fnc)
                obj.register(callback)
                return fnc
            return wrapper
        return decorator if self.nested else decorator()


class CreateApp(object):
    """Flask create_app pattern factory."""

    flask_class = Flask
    defaults = {
        'static_folder': None,
        'template_folder': None,
        }

    def __init__(self, import_name, **options):
        """
        Initialize.

        Arguments are passed to :class:`Flask` constructor.
        """
        self.import_name = import_name
        self.options = self.defaults.copy()
        self.options.update(options)
        self.registry = []

    def __call__(self):  # type: () -> Flask
        """Create Flask app instance."""
        app = self.flask_class(self.import_name, **self.options)
        with app.app_context():
            for fnc in self.registry:
                fnc()
        return app

    def register(self, fnc):
        """Register function to be called when app is initialized."""
        self.registry.append(fnc)
        return fnc

    before_first_request = AppDecoratorProxy('before_first_request')
    context_processor = AppDecoratorProxy('context_processor')
    url_defaults = AppDecoratorProxy('url_defaults')
    errorhandler = AppDecoratorProxy('errorhandler', nested=True)
    route = AppDecoratorProxy('route', nested=True)
