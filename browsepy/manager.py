#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import re
import sys
import argparse
import warnings
import collections

from flask import current_app
from werkzeug.utils import cached_property

from . import mimetype
from . import compat
from .compat import deprecated, usedoc


def defaultsnamedtuple(name, fields, defaults=None):
    '''
    Generate namedtuple with default values.

    :param name: name
    :param fields: iterable with field names
    :param defaults: iterable or mapping with field defaults
    :returns: defaultdict with given fields and given defaults
    :rtype: collections.defaultdict
    '''
    nt = collections.namedtuple(name, fields)
    nt.__new__.__defaults__ = (None,) * len(nt._fields)
    if isinstance(defaults, collections.Mapping):
        nt.__new__.__defaults__ = tuple(nt(**defaults))
    elif defaults:
        nt.__new__.__defaults__ = tuple(nt(*defaults))
    return nt


class PluginNotFoundError(ImportError):
    pass


class WidgetException(Exception):
    pass


class WidgetParameterException(WidgetException):
    pass


class InvalidArgumentError(ValueError):
    pass


class PluginManagerBase(object):
    '''
    Base plugin manager for plugin module loading and Flask extension logic.
    '''

    @property
    def namespaces(self):
        '''
        List of plugin namespaces taken from app config.
        '''
        return self.app.config['plugin_namespaces'] if self.app else []

    def __init__(self, app=None):
        if app is None:
            self.clear()
        else:
            self.init_app(app)

    def init_app(self, app):
        '''
        Initialize this Flask extension for given app.
        '''
        self.app = app
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['plugin_manager'] = self
        self.reload()

    def reload(self):
        '''
        Clear plugin manager state and reload plugins.

        This method will make use of :meth:`clear` and :meth:`load_plugin`,
        so all internal state will be cleared, and all plugins defined in
        :data:`self.app.config['plugin_modules']` will be loaded.
        '''
        self.clear()
        for plugin in self.app.config.get('plugin_modules', ()):
            self.load_plugin(plugin)

    def clear(self):
        '''
        Clear plugin manager state.
        '''
        pass

    def import_plugin(self, plugin):
        '''
        Import plugin by given name, looking at :attr:`namespaces`.

        :param plugin: plugin module name
        :type plugin: str
        :raises PluginNotFoundError: if not found on any namespace
        '''
        names = [
            '%s%s%s' % (namespace, '' if namespace[-1] == '_' else '.', plugin)
            if namespace else
            plugin
            for namespace in self.namespaces
            ]

        for name in names:
            if name in sys.modules:
                return sys.modules[name]

        for name in names:
            try:
                __import__(name)
                return sys.modules[name]
            except (ImportError, KeyError):
                pass

        raise PluginNotFoundError(
            'No plugin module %r found, tried %r' % (plugin, names),
            plugin, names)

    def load_plugin(self, plugin):
        '''
        Import plugin (see :meth:`import_plugin`) and load related data.

        :param plugin: plugin module name
        :type plugin: str
        :raises PluginNotFoundError: if not found on any namespace
        '''
        return self.import_plugin(plugin)


class RegistrablePluginManager(PluginManagerBase):
    '''
    Base plugin manager for plugin registration via :func:`register_plugin`
    functions at plugin module level.
    '''
    def load_plugin(self, plugin):
        '''
        Import plugin (see :meth:`import_plugin`) and load related data.

        If available, plugin's module-level :func:`register_plugin` function
        will be called with current plugin manager instance as first argument.

        :param plugin: plugin module name
        :type plugin: str
        :raises PluginNotFoundError: if not found on any namespace
        '''
        module = super(RegistrablePluginManager, self).load_plugin(plugin)
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)
        return module


class BlueprintPluginManager(RegistrablePluginManager):
    '''
    Manager for blueprint registration via :meth:`register_plugin` calls.

    Note: blueprints are not removed on `clear` nor reloaded on `reload`
    as flask does not allow it.
    '''
    def __init__(self, app=None):
        self._blueprint_known = set()
        super(BlueprintPluginManager, self).__init__(app=app)

    def register_blueprint(self, blueprint):
        '''
        Register given blueprint on curren app.

        This method is provided for using inside plugin's module-level
        :func:`register_plugin` functions.

        :param blueprint: blueprint object with plugin endpoints
        :type blueprint: flask.Blueprint
        '''
        if blueprint not in self._blueprint_known:
            self.app.register_blueprint(blueprint)
            self._blueprint_known.add(blueprint)


class WidgetPluginManager(RegistrablePluginManager):
    '''
    Plugin manager for widget registration.

    This class provides a dictionary of widget types at its
    :attr:`widget_types` attribute. They can be referenced by their keys on
    both :meth:`create_widget` and :meth:`register_widget` methods' `type`
    parameter, or instantiated directly and passed to :meth:`register_widget`
    via `widget` parameter.
    '''
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
        '''
        Clear plugin manager state.

        Registered widgets will be disposed after calling this method.
        '''
        self._widgets = []
        super(WidgetPluginManager, self).clear()

    def get_widgets(self, file=None, place=None):
        '''
        List registered widgets, optionally matching given criteria.

        :param file: optional file object will be passed to widgets' filter
                     functions.
        :type file: browsepy.file.Node or None
        :param place: optional template place hint.
        :type place: str
        :returns: list of widget instances
        :rtype: list of objects
        '''
        return list(self.iter_widgets(file, place))

    @classmethod
    def _resolve_widget(cls, file, widget):
        '''
        Resolve widget callable properties into static ones.

        :param file: file will be used to resolve callable properties.
        :type file: browsepy.file.Node
        :param widget: widget instance optionally with callable properties
        :type widget: object
        :returns: a new widget instance of the same type as widget parameter
        :rtype: object
        '''
        return widget.__class__(*[
            value(file) if callable(value) else value
            for value in widget
            ])

    def iter_widgets(self, file=None, place=None):
        '''
        Iterate registered widgets, optionally matching given criteria.

        :param file: optional file object will be passed to widgets' filter
                     functions.
        :type file: browsepy.file.Node or None
        :param place: optional template place hint.
        :type place: str
        :yields: widget instances
        :ytype: object
        '''
        for filter, dynamic, cwidget in self._widgets:
            try:
                if file and filter and not filter(file):
                    continue
            except BaseException as e:
                # Exception is handled  as this method execution is deffered,
                # making hard to debug for plugin developers.
                warnings.warn(
                    'Plugin action filtering failed with error: %s' % e,
                    RuntimeWarning
                    )
                continue
            if place and place != cwidget.place:
                continue
            if file and dynamic:
                cwidget = self._resolve_widget(file, cwidget)
            yield cwidget

    def create_widget(self, place, type, file=None, **kwargs):
        '''
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
        '''
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
        '''
        Create (see :meth:`create_widget`) or use provided widget and register
        it.

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
        '''
        if bool(widget) == bool(place or type):
            raise InvalidArgumentError(
                'register_widget takes either place and type or widget'
                )
        widget = widget or self.create_widget(place, type, **kwargs)
        dynamic = any(map(callable, widget))
        self._widgets.append((filter, dynamic, widget))
        return widget


class MimetypePluginManager(RegistrablePluginManager):
    '''
    Plugin manager for mimetype-function registration.
    '''
    _default_mimetype_functions = (
        mimetype.by_python,
        mimetype.by_file,
        mimetype.by_default,
    )

    def clear(self):
        '''
        Clear plugin manager state.

        Registered mimetype functions will be disposed after calling this
        method.
        '''
        self._mimetype_functions = list(self._default_mimetype_functions)
        super(MimetypePluginManager, self).clear()

    def get_mimetype(self, path):
        '''
        Get mimetype of given path calling all registered mime functions (and
        default ones).

        :param path: filesystem path of file
        :type path: str
        :returns: mimetype
        :rtype: str
        '''
        for fnc in self._mimetype_functions:
            mime = fnc(path)
            if mime:
                return mime
        return mimetype.by_default(path)

    def register_mimetype_function(self, fnc):
        '''
        Register mimetype function.

        Given function must accept a filesystem path as string and return
        a mimetype string or None.

        :param fnc: callable accepting a path string
        :type fnc: callable
        '''
        self._mimetype_functions.insert(0, fnc)


class ArgumentPluginManager(PluginManagerBase):
    '''
    Plugin manager for command-line argument registration.

    This function is used by browsepy's :mod:`__main__` module in order
    to attach extra arguments at argument-parsing time.

    This is done by :meth:`load_arguments` which imports all plugin modules
    and calls their respective :func:`register_arguments` module-level
    function.
    '''
    _argparse_kwargs = {'add_help': False}
    _argparse_arguments = argparse.Namespace()

    def extract_plugin_arguments(self, plugin):
        '''
        Given a plugin name, extracts its registered_arguments as an
        iterable of (args, kwargs) tuples.

        :param plugin: plugin name
        :type plugin: str
        :returns: iterable if (args, kwargs) tuples.
        :rtype: iterable
        '''
        module = self.import_plugin(plugin)
        if hasattr(module, 'register_arguments'):
            manager = ArgumentPluginManager()
            module.register_arguments(manager)
            return manager._argparse_argkwargs
        return ()

    def load_arguments(self, argv, base=None):
        '''
        Process given argument list based on registered arguments and given
        optional base :class:`argparse.ArgumentParser` instance.

        This method saves processed arguments on itself, and this state won't
        be lost after :meth:`clean` calls.

        Processed argument state will be available via :meth:`get_argument`
        method.

        :param argv: command-line arguments (without command itself)
        :type argv: iterable of str
        :param base: optional base :class:`argparse.ArgumentParser` instance.
        :type base: argparse.ArgumentParser or None
        :returns: argparse.Namespace instance with processed arguments as
                  given by :meth:`argparse.ArgumentParser.parse_args`.
        :rtype: argparse.Namespace
        '''
        plugin_parser = argparse.ArgumentParser(add_help=False)
        plugin_parser.add_argument('--plugin', action='append', default=[])
        parent = base or plugin_parser
        parser = argparse.ArgumentParser(
            parents=(parent,),
            add_help=False,
            **getattr(parent, 'defaults', {})
            )
        plugins = [
            plugin
            for plugins in plugin_parser.parse_known_args(argv)[0].plugin
            for plugin in plugins.split(',')
            ]
        for plugin in sorted(set(plugins), key=plugins.index):
            arguments = self.extract_plugin_arguments(plugin)
            if arguments:
                group = parser.add_argument_group('%s arguments' % plugin)
                for argargs, argkwargs in arguments:
                    group.add_argument(*argargs, **argkwargs)
        self._argparse_arguments = parser.parse_args(argv)
        return self._argparse_arguments

    def clear(self):
        '''
        Clear plugin manager state.

        Registered command-line arguments will be disposed after calling this
        method.
        '''
        self._argparse_argkwargs = []
        super(ArgumentPluginManager, self).clear()

    def register_argument(self, *args, **kwargs):
        '''
        Register command-line argument.

        All given arguments will be passed directly to
        :meth:`argparse.ArgumentParser.add_argument` calls by
        :meth:`load_arguments` method.

        See :meth:`argparse.ArgumentParser.add_argument` documentation for
        further information.
        '''
        self._argparse_argkwargs.append((args, kwargs))

    def get_argument(self, name, default=None):
        '''
        Get argument value from last :meth:`load_arguments` call.

        Keep in mind :meth:`argparse.ArgumentParser.parse_args` generates
        its own command-line arguments if `dest` kwarg is not provided,
        so ie. `--my-option` became available as `my_option`.

        :param name: command-line argument name
        :type name: str
        :param default: default value if parameter is not found
        :returns: command-line argument or default value
        '''
        return getattr(self._argparse_arguments, name, default)


class MimetypeActionPluginManager(WidgetPluginManager, MimetypePluginManager):
    '''
    Deprecated plugin API
    '''

    _deprecated_places = {
        'javascript': 'scripts',
        'style': 'styles',
        'button': 'entry-actions',
        'link': 'entry-link',
        }

    @classmethod
    def _mimetype_filter(cls, mimetypes):
        widget_mimetype_re = re.compile(
            '^%s$' % '$|^'.join(
                map(re.escape, mimetypes)
                ).replace('\\*', '[^/]+')
            )

        def handler(f):
            return widget_mimetype_re.match(f.type) is not None

        return handler

    def _widget_attrgetter(self, widget, name):
        def handler(f):
            app = f.app or self.app or current_app
            with app.app_context():
                return getattr(widget.for_file(f), name)
        return handler

    def _widget_props(self, widget, endpoint=None, mimetypes=(),
                      dynamic=False):
        type = getattr(widget, '_type', 'base')
        fields = self.widget_types[type]._fields
        with self.app.app_context():
            props = {
                name: self._widget_attrgetter(widget, name)
                for name in fields
                if hasattr(widget, name)
                }
        props.update(
            type=type,
            place=self._deprecated_places.get(widget.place),
            )
        if dynamic:
            props['filter'] = self._mimetype_filter(mimetypes)
        if 'endpoint' in fields:
            props['endpoint'] = endpoint
        return props

    @usedoc(WidgetPluginManager.__init__)
    def __init__(self, app=None):
        self._action_widgets = []
        super(MimetypeActionPluginManager, self).__init__(app=app)

    @usedoc(WidgetPluginManager.clear)
    def clear(self):
        self._action_widgets[:] = ()
        super(MimetypeActionPluginManager, self).clear()

    @cached_property
    def _widget(self):
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            from . import widget
        return widget

    @cached_property
    @deprecated('Deprecated attribute action_class')
    def action_class(self):
        return collections.namedtuple(
            'MimetypeAction',
            ('endpoint', 'widget')
            )

    @cached_property
    @deprecated('Deprecated attribute style_class')
    def style_class(self):
        return self._widget.StyleWidget

    @cached_property
    @deprecated('Deprecated attribute button_class')
    def button_class(self):
        return self._widget.ButtonWidget

    @cached_property
    @deprecated('Deprecated attribute javascript_class')
    def javascript_class(self):
        return self._widget.JavascriptWidget

    @cached_property
    @deprecated('Deprecated attribute link_class')
    def link_class(self):
        return self._widget.LinkWidget

    @deprecated('Deprecated method register_action')
    def register_action(self, endpoint, widget, mimetypes=(), **kwargs):
        props = self._widget_props(widget, endpoint, mimetypes, True)
        self.register_widget(**props)
        self._action_widgets.append((widget, props['filter'], endpoint))

    @deprecated('Deprecated method get_actions')
    def get_actions(self, file):
        return [
            self.action_class(endpoint, deprecated.for_file(file))
            for deprecated, filter, endpoint in self._action_widgets
            if endpoint and filter(file)
            ]

    @usedoc(WidgetPluginManager.register_widget)
    def register_widget(self, place=None, type=None, widget=None, filter=None,
                        **kwargs):
        if isinstance(place or widget, self._widget.WidgetBase):
            warnings.warn(
                'Deprecated use of register_widget',
                category=DeprecationWarning
                )
            widget = place or widget
            props = self._widget_props(widget)
            self.register_widget(**props)
            self._action_widgets.append((widget, None, None))
            return
        return super(MimetypeActionPluginManager, self).register_widget(
            place=place, type=type, widget=widget, filter=filter, **kwargs)

    @usedoc(WidgetPluginManager.get_widgets)
    def get_widgets(self, file=None, place=None):
        if isinstance(file, compat.basestring) or \
          place in self._deprecated_places:
            warnings.warn(
                'Deprecated use of get_widgets',
                category=DeprecationWarning
                )
            place = file or place
            return [
                widget
                for widget, filter, endpoint in self._action_widgets
                if not (filter or endpoint) and place == widget.place
                ]
        return super(MimetypeActionPluginManager, self).get_widgets(
            file=file, place=place)


class PluginManager(MimetypeActionPluginManager,
                    BlueprintPluginManager, WidgetPluginManager,
                    MimetypePluginManager, ArgumentPluginManager):
    '''
    Main plugin manager

    Provides:
        * Plugin module loading and Flask extension logic.
        * Plugin registration via :func:`register_plugin` functions at plugin
          module level.
        * Plugin blueprint registration via :meth:`register_plugin` calls.
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
    '''
    def clear(self):
        '''
        Clear plugin manager state.

        Registered widgets will be disposed after calling this method.

        Registered mimetype functions will be disposed after calling this
        method.

        Registered command-line arguments will be disposed after calling this
        method.
        '''
        super(PluginManager, self).clear()
