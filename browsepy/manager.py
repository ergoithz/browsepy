#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import argparse
import warnings
import collections

from . import mimetype


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


class PluginManagerBase(object):

    @property
    def namespaces(self):
        return self.app.config['plugin_namespaces'] if self.app else []

    def __init__(self, app=None):
        if app is None:
            self.clear()
        else:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['plugin_manager'] = self
        self.reload()

    def reload(self):
        self.clear()
        for plugin in self.app.config.get('plugin_modules', ()):
            self.load_plugin(plugin)

    def clear(self):
        pass

    def import_plugin(self, plugin):
        names = [
            '%s.%s' % (namespace, plugin) if namespace else plugin
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
        return self.import_plugin(plugin)


class RegistrablePluginManager(PluginManagerBase):
    def load_plugin(self, plugin):
        module = super(RegistrablePluginManager, self).load_plugin(plugin)
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)
        return module


class BlueprintPluginManager(RegistrablePluginManager):
    '''
    Note: blueprints are not removed on `clear` nor reloaded on `reload`
    as flask does not allow it.
    '''
    def __init__(self, app=None):
        self._blueprint_known = set()
        super(BlueprintPluginManager, self).__init__(app=app)

    def register_blueprint(self, blueprint):
        if blueprint not in self._blueprint_known:
            self.app.register_blueprint(blueprint)
            self._blueprint_known.add(blueprint)


class WidgetPluginManager(RegistrablePluginManager):
    widget_types = {
        'base': defaultsnamedtuple(
            'Widget',
            ('place', 'type')),
        'link': defaultsnamedtuple(
            'Link',
            ('place', 'type', 'css', 'icon', 'text', 'endpoint', 'href'),
            {
                'text': lambda f: f.name,
                'icon': lambda f: f.category
            }),
        'button': defaultsnamedtuple(
            'Button',
            ('place', 'type', 'css', 'text', 'endpoint', 'href')),
        'upload': defaultsnamedtuple(
            'Upload',
            ('place', 'type', 'css', 'text', 'endpoint', 'action')),
        'stylesheet': defaultsnamedtuple(
            'Stylesheet',
            ('place', 'type', 'endpoint', 'filename', 'href')),
        'script': defaultsnamedtuple(
            'Script',
            ('place', 'type', 'endpoint', 'filename', 'src')),
        'html': defaultsnamedtuple(
            'Html',
            ('place', 'type', 'html')),
    }

    def clear(self):
        self._widgets = []
        super(WidgetPluginManager, self).clear()

    def get_widgets(self, file=None, place=None):
        return list(self.iter_widgets(file, place))

    def _resolve_widget(self, file, widget):
        return widget.__class__(*[
            value(file) if callable(value) else value
            for value in widget
            ])

    def iter_widgets(self, file=None, place=None):
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

    def create_widget(self, place=None, type=None, file=None, **kwargs):
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
        widget = widget or self.create_widget(place, type, **kwargs)
        dynamic = any(map(callable, widget))
        self._widgets.append((filter, dynamic, widget))


class MimetypePluginManager(RegistrablePluginManager):
    _default_mimetype_functions = (
        mimetype.by_python,
        mimetype.by_file,
        mimetype.by_default,
    )

    def clear(self):
        self._mimetype_functions = list(self._default_mimetype_functions)
        super(MimetypePluginManager, self).clear()

    def get_mimetype(self, path):
        for fnc in self._mimetype_functions:
            mime = fnc(path)
            if mime:
                return mime
        return mimetype.by_default(path)

    def register_mimetype_function(self, fnc):
        self._mimetype_functions.insert(0, fnc)


class ArgumentPluginManager(PluginManagerBase):
    _argparse_kwargs = {'add_help': False}
    _argparse_arguments = argparse.Namespace()

    def load_arguments(self, argv, base=None):
        plugin_parser = argparse.ArgumentParser(add_help=False)
        plugin_parser.add_argument(
            '--plugin',
            type=lambda x: x.split(',') if x else [],
            default=[]
            )
        parser = argparse.ArgumentParser(
            parents=(base or plugin_parser,),
            add_help=False
            )
        for plugin in plugin_parser.parse_known_args(argv)[0].plugin:
            module = self.import_plugin(plugin)
            if hasattr(module, 'register_arguments'):
                manager = ArgumentPluginManager()
                module.register_arguments(manager)
                group = parser.add_argument_group('%s arguments' % plugin)
                for argargs, argkwargs in manager._argparse_argkwargs:
                    group.add_argument(*argargs, **argkwargs)
        self._argparse_arguments = parser.parse_args(argv)
        return self._argparse_arguments

    def clear(self):
        self._argparse_argkwargs = []
        super(ArgumentPluginManager, self).clear()

    def register_argument(self, *args, **kwargs):
        self._argparse_argkwargs.append((args, kwargs))

    def get_argument(self, name, default=None):
        return getattr(self._argparse_arguments, name, default)


class PluginManager(BlueprintPluginManager, WidgetPluginManager,
                    MimetypePluginManager, ArgumentPluginManager):
    pass
