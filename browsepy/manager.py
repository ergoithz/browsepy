"""Browsepy plugin manager classes."""

import typing
import types
import os.path
import pkgutil
import argparse
import functools
import warnings
import importlib

from cookieman import CookieMan

from . import mimetype
from . import compat
from . import utils
from . import file

from .compat import cached_property
from .utils import defaultsnamedtuple
from .exceptions import PluginNotFoundError, InvalidArgumentError, \
                        WidgetParameterException


class PluginManagerBase(object):
    """Base plugin manager with loading and Flask extension logic."""

    _pyfile_extensions = ('.py', '.pyc', '.pyd', '.pyo')

    get_module = staticmethod(importlib.import_module)
    plugin_module_methods = ()  # type: typing.Tuple[str, ...]

    @property
    def namespaces(self):
        # type: () -> typing.Iterable[str]
        """
        List plugin namespaces taken from app config.

        :returns: list of plugin namespaces
        :rtype: typing.List[str]
        """
        return self.app.config.get('PLUGIN_NAMESPACES', []) if self.app else []

    def __init__(self, app=None):
        # type app: typing.Optional[flask.Flask]
        """
        Initialize.

        :param app: flask application
        """
        if app is None:
            self.clear()
        else:
            self.init_app(app)

    def init_app(self, app):
        # type app: flask.Flask
        """
        Initialize this Flask extension for given app.

        :param app: flask application
        """
        self.app = utils.solve_local(app)
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['plugin_manager'] = self
        self.reload()

    def reload(self):
        """
        Clear plugin manager state and reload plugins.

        This method will make use of :meth:`clear` and :meth:`load_plugin`,
        so all internal state will be cleared, and all plugins defined in
        :data:`self.app.config['PLUGIN_MODULES']` will be loaded.
        """
        self.clear()
        for plugin in self.app.config.get('PLUGIN_MODULES', ()):
            self.load_plugin(plugin)

    def clear(self):
        """Clear plugin manager state."""
        pass

    def _iter_modules(self, prefix):
        """Iterate thru all root modules containing given prefix."""
        for finder, name, ispkg in pkgutil.iter_modules():
            if name.startswith(prefix):
                yield name

    def _content_import_name(self, module, item, prefix):
        # type: (str, str, str) -> typing.Optional[str]
        """Get importable module contnt import name."""
        res = compat.res
        name = '%s.%s' % (module, item)
        if name.startswith(prefix):
            for ext in self._pyfile_extensions:
                if name.endswith(ext):
                    return name[:-len(ext)]
            if not res.is_resource(module, item):
                return name
        return None

    def _iter_submodules(self, prefix):
        # type: (str) -> typing.Generator[str, None, None]
        """Iterate thru all modules with an absolute prefix."""
        res = compat.res
        parent = prefix.rsplit('.', 1)[0]
        for base in (prefix, parent):
            try:
                for item in res.contents(base):
                    content = self._content_import_name(base, item, prefix)
                    if content:
                        yield content
            except ImportError:
                pass

    def _iter_namespace_modules(self):
        # type: () -> typing.Generator[typing.Tuple[str, str], None, None]
        """Iterate module names under namespaces."""
        nameset = set()  # type: typing.Set[str]
        for prefix in filter(None, self.namespaces):
            name_iter_fnc = (
                self._iter_submodules
                if '.' in prefix else
                self._iter_modules
                )
            for name in name_iter_fnc(prefix):
                if name not in nameset:
                    nameset.add(name)
                    yield prefix, name

    def _iter_plugin_modules(self):
        """
        Iterate plugin modules.

        This generator yields both full qualified name and short plugin
        names.
        """
        shortset = set()  # type: typing.Set[str]
        for namespace, name in self._iter_namespace_modules():
            plugin = self._get_plugin_module(name)
            if plugin:
                short = name[len(namespace):].lstrip('.').replace('_', '-')
                yield (
                    name,
                    None if short in shortset or '.' in short else short
                    )
                shortset.add(short)

    def _get_plugin_module(self, name):
        """Import plugin module from absolute name."""
        try:
            module = self.get_module(name)
            for name in self.plugin_module_methods:
                if callable(getattr(module, name, None)):
                    return module
        except ImportError:
            pass
        return None

    @cached_property
    def available_plugins(self):
        # type: () -> typing.List[types.ModuleType]
        """Iterate through all loadable plugins on typical paths."""
        return list(self._iter_plugin_modules())

    def import_plugin(self, plugin):
        # type: (str) -> types.ModuleType
        """
        Import plugin by given name, looking at :attr:`namespaces`.

        :param plugin: plugin module name
        :raises PluginNotFoundError: if not found on any namespace
        """
        plugin = plugin.replace('-', '_')
        names = [
            '%s%s%s' % (
                namespace,
                '.' if namespace and namespace[-1] not in '._' else '',
                plugin,
                )
            for namespace in self.namespaces
            ]
        names = sorted(frozenset(names), key=names.index)
        for name in names:
            module = self._get_plugin_module(name)
            if module:
                return module
        raise PluginNotFoundError(
            'No plugin module %r found, tried %r' % (plugin, names),
            plugin, names)

    def load_plugin(self, plugin):
        # type: (str) -> types.ModuleType
        """
        Import plugin (see :meth:`import_plugin`) and load related data.

        :param plugin: plugin module name
        :raises PluginNotFoundError: if not found on any namespace
        """
        return self.import_plugin(plugin)


class RegistrablePluginManager(PluginManagerBase):
    """
    Plugin registration manager.

    Plugin registration requires a :func:`register_plugin` function at
    the plugin module level.
    """

    plugin_module_methods = ('register_plugin',)

    def load_plugin(self, plugin):
        """
        Import plugin (see :meth:`import_plugin`) and load related data.

        If available, plugin's module-level :func:`register_plugin` function
        will be called with current plugin manager instance as first argument.

        :param plugin: plugin module name
        :type plugin: str
        :raises PluginNotFoundError: if not found on any namespace
        """
        module = super(RegistrablePluginManager, self).load_plugin(plugin)
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)
        return module


class BlueprintPluginManager(PluginManagerBase):
    """
    Plugin blueprint registration manager.

    Blueprint registration done via :meth:`register_blueprint`
    calls inside plugin :func:`register_plugin`.

    Note: blueprints are not removed on `clear` nor reloaded on `reload`
    as flask does not allow it, consider creating a new clean
    :class:`flask.Flask` browsepy app by using :func:`browsepy.create_app`.

    """

    def __init__(self, app=None):
        """Initialize."""
        self._blueprint_known = set()
        super(BlueprintPluginManager, self).__init__(app=app)

    def register_blueprint(self, blueprint):
        """
        Register given blueprint on curren app.

        This method is intended to be used on plugin's module-level
        :func:`register_plugin` functions.

        :param blueprint: blueprint object with plugin endpoints
        :type blueprint: flask.Blueprint
        """
        if blueprint not in self._blueprint_known:
            self.app.register_blueprint(blueprint)
            self._blueprint_known.add(blueprint)


class ExcludePluginManager(PluginManagerBase):
    """
    Plugin node exclusion registration manager.

    Exclude-function registration done via :meth:`register_exclude_fnc`
    calls inside plugin :func:`register_plugin`.

    """

    def __init__(self, app=None):
        """Initialize."""
        self._exclude_functions = set()
        super(ExcludePluginManager, self).__init__(app=app)

    def register_exclude_function(self, exclude_fnc):
        """
        Register given exclude-function on current app.

        This method is intended to be used on plugin's module-level
        :func:`register_plugin` functions.

        :param blueprint: blueprint object with plugin endpoints
        :type blueprint: flask.Blueprint
        """
        self._exclude_functions.add(exclude_fnc)

    def check_excluded(self, path, follow_symlinks=True):
        """
        Check if given path is excluded.

        Followed symlinks are checked against directory base for safety.

        :param path: absolute path to check against config and plugins
        :type path: str
        :param follow_symlinks: wether or not follow_symlinks
        :type follow_symlinks: bool
        :return: wether if path should be excluded or not
        :rtype: bool
        """
        exclude_fnc = self.app.config.get('EXCLUDE_FNC')
        if exclude_fnc and exclude_fnc(path):
            return True
        for fnc in self._exclude_functions:
            if fnc(path):
                return True
        if follow_symlinks:
            realpath = os.path.realpath(path)
            dirbase = self.app.config.get('DIRECTORY_BASE')
            return realpath != path and (
                dirbase and not file.check_base(path, dirbase) or
                self.check_excluded(realpath, follow_symlinks=False)
                )
        return False

    def clear(self):
        """
        Clear plugin manager state.

        Registered exclude functions will be disposed.
        """
        self._exclude_functions.clear()
        super(ExcludePluginManager, self).clear()


class WidgetPluginManager(PluginManagerBase):
    """
    Plugin widget registration manager.

    This class provides a dictionary of supported widget types available as
    :attr:`widget_types` attribute. They can be referenced by their keys on
    both :meth:`create_widget` and :meth:`register_widget` methods' `type`
    parameter, or instantiated directly and passed to :meth:`register_widget`
    via `widget` parameter.
    """

    widget_types = {
        'base': defaultsnamedtuple(
            'Widget',
            ('place', 'type')),
        'link': defaultsnamedtuple(
            'Link',
            ('place', 'type', 'css', 'icon', 'text', 'endpoint', 'href'),
            {
                'type': 'link',
                'text': lambda f: f.name,
                'icon': lambda f: f.category
                }),
        'button': defaultsnamedtuple(
            'Button',
            ('place', 'type', 'css', 'text', 'endpoint', 'href'),
            {'type': 'button'}),
        'upload': defaultsnamedtuple(
            'Upload',
            ('place', 'type', 'css', 'text', 'endpoint', 'action'),
            {'type': 'upload'}),
        'stylesheet': defaultsnamedtuple(
            'Stylesheet',
            ('place', 'type', 'endpoint', 'filename', 'href'),
            {'type': 'stylesheet'}),
        'script': defaultsnamedtuple(
            'Script',
            ('place', 'type', 'endpoint', 'filename', 'src'),
            {'type': 'script'}),
        'html': defaultsnamedtuple(
            'Html',
            ('place', 'type', 'html'),
            {'type': 'html'}),
        }

    def clear(self):
        """
        Clear plugin manager state.

        Registered widgets will be disposed after calling this method.
        """
        self._widgets = []
        super(WidgetPluginManager, self).clear()

    def get_widgets(self, file=None, place=None):
        """
        List registered widgets, optionally matching given criteria.

        :param file: optional file object will be passed to widgets'
                     filter functions.
        :type file: browsepy.file.Node or None
        :param place: optional template place hint.
        :type place: str
        :returns: list of widget instances
        :rtype: list of objects
        """
        return list(self.iter_widgets(file, place))

    @classmethod
    def _resolve_widget(cls, file, widget):
        """
        Resolve widget callable properties into static ones.

        :param file: file will be used to resolve callable properties.
        :type file: browsepy.file.Node
        :param widget: widget instance optionally with callable properties
        :type widget: object
        :returns: a new widget instance of the same type as widget parameter
        :rtype: object
        """
        return widget.__class__(*[
            value(file) if callable(value) else value
            for value in widget
            ])

    def iter_widgets(self, file=None, place=None):
        """
        Iterate registered widgets, optionally matching given criteria.

        :param file: optional file object will be passed to widgets' filter
                     functions.
        :type file: browsepy.file.Node or None
        :param place: optional template place hint.
        :type place: str
        :yields: widget instances
        :ytype: object
        """
        for filter, dynamic, cwidget in self._widgets:
            try:
                if (
                  (file and filter and not filter(file)) or
                  (place and place != cwidget.place)
                  ):
                    continue
            except BaseException as e:
                # Exception is catch as this execution is deferred,
                # making debugging harder for plugin developers.
                warnings.warn(
                    'Plugin action filtering failed with error: %s' % e,
                    RuntimeWarning
                    )
                continue
            if file and dynamic:
                cwidget = self._resolve_widget(file, cwidget)
            yield cwidget

    def create_widget(self, place, type, file=None, **kwargs):
        """
        Create a widget object based on given arguments.

        If file object is provided, callable arguments will be resolved:
        its return value will be used after calling them with file as first
        parameter.

        All extra `kwargs` parameters will be passed to widget constructor.

        :param place: place hint where widget should be shown.
        :type place: str
        :param type: widget type name as taken from :attr:`widget_types` dict
                     keys.
        :type type: str
        :param file: optional file object for widget attribute resolving
        :type type: browsepy.files.Node or None
        :returns: widget instance
        :rtype: object
        """
        widget_class = self.widget_types.get(type, self.widget_types['base'])
        kwargs.update(place=place, type=type)
        try:
            element = widget_class(**kwargs)
        except TypeError as e:
            message = e.args[0] if e.args else ''
            if (
              'unexpected keyword argument' in message or
              'required positional argument' in message
              ):
                raise WidgetParameterException(
                    'type %s; %s; available: %r'
                    % (type, message, widget_class._fields)
                    )
            raise e
        if file and any(map(callable, element)):
            return self._resolve_widget(file, element)
        return element

    def register_widget(self, place=None, type=None, widget=None, filter=None,
                        **kwargs):
        """
        Register a widget, optionally creating it with :meth:`create_widget`.

        This method provides this dual behavior in order to simplify widget
        creation-registration on an functional single step without sacrifycing
        the reusability of a object-oriented approach.

        :param place: where widget should be placed. This param conflicts
                      with `widget` argument.
        :type place: str or None
        :param type: widget type name as taken from :attr:`widget_types` dict
                     keys. This param conflicts with `widget` argument.
        :type type: str or None
        :param widget: optional widget object will be used as is. This param
                       conflicts with both place and type arguments.
        :type widget: object or None
        :raises TypeError: if both widget and place or type are provided at
                           the same time (they're mutually exclusive).
        :returns: created or given widget object
        :rtype: object
        """
        if bool(widget) == bool(place or type):
            raise InvalidArgumentError(
                'register_widget takes either place and type or widget'
                )
        widget = widget or self.create_widget(place, type, **kwargs)
        dynamic = any(map(callable, widget))
        self._widgets.append((filter, dynamic, widget))
        return widget


class MimetypePluginManager(RegistrablePluginManager):
    """Plugin mimetype function registration manager."""

    _default_mimetype_functions = mimetype.alternatives

    def clear(self):
        """
        Clear plugin manager state.

        Registered mimetype functions will be disposed after calling this
        method.
        """
        self._mimetype_functions = list(self._default_mimetype_functions)
        super(MimetypePluginManager, self).clear()

    def get_mimetype(self, path):
        """
        Get mimetype of given path based on registered mimetype functions.

        :param path: filesystem path of file
        :type path: str
        :returns: mimetype
        :rtype: str
        """
        for fnc in self._mimetype_functions:
            mime = fnc(path)
            if mime:
                return mime
        return mimetype.by_default(path)

    def register_mimetype_function(self, fnc):
        """
        Register mimetype function.

        Given function must accept a filesystem path as string and return
        a mimetype string or None.

        :param fnc: callable accepting a path string
        :type fnc: callable
        """
        self._mimetype_functions.insert(0, fnc)


class SessionPluginManager(PluginManagerBase):
    """Plugin session shrink function registration manager."""

    def register_session(self, key_or_keys, shrink_fnc=None):
        """
        Register shrink function for specific session key or keys.

        Can be used as decorator.

        Usage:
        >>> @manager.register_session('my_session_key')
        ... def my_shrink_fnc(data):
        ...     del data['my_session_key']
        ...     return data

        :param key_or_keys: key or iterable of keys would be affected
        :type key_or_keys: Union[str, Iterable[str]]
        :param shrink_fnc: shrinking function (optional for decorator)
        :type shrink_fnc: cookieman.abc.ShrinkFunction
        :returns: either original given shrink_fnc or decorator
        :rtype: cookieman.abc.ShrinkFunction
        """
        interface = self.app.session_interface
        if isinstance(interface, CookieMan):
            return interface.register(key_or_keys, shrink_fnc)
        return shrink_fnc


class ArgumentPluginManager(PluginManagerBase):
    """
    Plugin command-line argument registration manager.

    This function is used by browsepy's :mod:`__main__` module in order
    to attach extra arguments at argument-parsing time.

    This is done by :meth:`load_arguments` which imports all plugin modules
    and calls their respective :func:`register_arguments` module-level
    function.
    """

    _argparse_kwargs = {'add_help': False}
    _argparse_arguments = argparse.Namespace()

    plugin_module_methods = ('register_arguments',)

    @cached_property
    def _default_argument_parser(self):
        parser = compat.SafeArgumentParser()
        parser.add_argument('--plugin', action='append', default=[])
        parser.add_argument('--help', action='store_true')
        parser.add_argument('--help-all', action='store_true')
        return parser

    def extract_plugin_arguments(self, plugin):
        """
        Extract registered argument pairs from given plugin name.

        Arguments are returned as an iterable of (args, kwargs) tuples.

        :param plugin: plugin name
        :type plugin: str
        :returns: iterable if (args, kwargs) tuples.
        :rtype: iterable
        """
        module = self.import_plugin(plugin)
        register_arguments = getattr(module, 'register_arguments', None)
        if callable(register_arguments):
            manager = ArgumentPluginManager()
            register_arguments(manager)
            return manager._argparse_argkwargs
        return ()

    def _plugin_argument_parser(self, base=None):
        plugins = self.available_plugins
        parent = base or self._default_argument_parser
        prop = functools.partial(getattr, parent)
        epilog = prop('epilog') or ''
        if plugins:
            epilog += '\n\navailable plugins:\n%s' % '\n'.join(
                '  %s, %s' % (short, name) if short else '  %s' % name
                for name, short in plugins
                )
        return compat.SafeArgumentParser(
            parents=[parent],
            prog=prop('prog', self.app.config['APPLICATION_NAME']),
            description=prop('description'),
            formatter_class=prop('formatter_class', compat.HelpFormatter),
            epilog=epilog.strip(),
            )

    def _plugin_arguments(self, parser, options):
        plugins = [
            plugin
            for plugins in options.plugin
            for plugin in plugins.split(',')
            ]

        if options.help_all:
            plugins.extend(
                short if short else name
                for name, short in self.available_plugins
                if not (name in plugins or short in plugins)
                )

        for plugin in sorted(set(plugins), key=plugins.index):
            arguments = self.extract_plugin_arguments(plugin)
            if arguments:
                yield plugin, arguments

    def load_arguments(
            self,
            argv,  # type: typing.Iterable[str]
            base=None,  # type: typing.Optional[argparse.ArgumentParser]
            ):  # type: (...) -> argparse.Namespace
        """
        Process command line argument iterable.

        Argument processing is based on registered arguments and given
        optional base :class:`argparse.ArgumentParser` instance.

        This method saves processed arguments on itself, and this state won't
        be lost after :meth:`clean` calls.

        Processed argument state will be available via :meth:`get_argument`
        method.

        :param argv: command-line arguments (without command itself)
        :param base: optional base :class:`argparse.ArgumentParser` instance.
        :returns: argparse.Namespace instance with processed arguments as
                  given by :meth:`argparse.ArgumentParser.parse_args`.
        :rtype: argparse.Namespace
        """
        parser = self._plugin_argument_parser(base)
        options, _ = parser.parse_known_args(argv)

        for plugin, arguments in self._plugin_arguments(parser, options):
            group = parser.add_argument_group('%s arguments' % plugin)
            for argargs, argkwargs in arguments:
                group.add_argument(*argargs, **argkwargs)

        if options.help or options.help_all:
            parser.print_help()
            parser.exit()

        self._argparse_arguments = parser.parse_args(argv)
        return self._argparse_arguments

    def clear(self):
        """
        Clear plugin manager state.

        Registered command-line arguments will be disposed after calling this
        method.
        """
        self._argparse_argkwargs = []
        super(ArgumentPluginManager, self).clear()

    def register_argument(self, *args, **kwargs):
        """
        Register command-line argument.

        All given arguments will be passed directly to
        :meth:`argparse.ArgumentParser.add_argument` calls by
        :meth:`load_arguments` method.

        See :meth:`argparse.ArgumentParser.add_argument` documentation for
        further information.
        """
        self._argparse_argkwargs.append((args, kwargs))

    def get_argument(self, name, default=None):
        """
        Get argument value from last :meth:`load_arguments` call.

        Keep in mind :meth:`argparse.ArgumentParser.parse_args` generates
        its own command-line arguments if `dest` kwarg is not provided,
        so ie. `--my-option` became available as `my_option`.

        :param name: command-line argument name
        :type name: str
        :param default: default value if parameter is not found
        :returns: command-line argument or default value
        """
        return getattr(self._argparse_arguments, name, default)


@file.Node.register_manager_class
class PluginManager(BlueprintPluginManager,
                    ExcludePluginManager,
                    WidgetPluginManager,
                    MimetypePluginManager,
                    SessionPluginManager,
                    ArgumentPluginManager):
    """
    Main plugin manager.

    Provides:
        * Plugin module loading and Flask extension logic.
        * Plugin registration via :func:`register_plugin` functions at plugin
          module level.
        * Plugin blueprint registration via :meth:`register_plugin` calls.
        * Plugin app-level file exclusion via exclude-function registration
          via :meth:`register_exclude_fnc`.
        * Widget registration via :meth:`register_widget` method.
        * Mimetype function registration via :meth:`register_mimetype_function`
          method.
        * Command-line argument registration calling :func:`register_arguments`
          at plugin module level and providing :meth:`register_argument`
          method.

    This class also provides a dictionary of widget types at its
    :attr:`widget_types` attribute. They can be referenced by their keys on
    both :meth:`create_widget` and :meth:`register_widget` methods' `type`
    parameter, or instantiated directly and passed to :meth:`register_widget`
    via `widget` parameter.
    """

    plugin_module_methods = sum((
        parent.plugin_module_methods
        for parent in (
            BlueprintPluginManager,
            ExcludePluginManager,
            WidgetPluginManager,
            MimetypePluginManager,
            SessionPluginManager,
            ArgumentPluginManager)
        ), ())

    def clear(self):
        """
        Clear plugin manager state.

        Registered widgets will be disposed after calling this method.

        Registered mimetype functions will be disposed after calling this
        method.

        Registered command-line arguments will be disposed after calling this
        method.
        """
        super(PluginManager, self).clear()
