#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import argparse
import warnings

from . import mimetype
from . import widget


class PluginNotFoundError(ImportError):
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
    widget_class = widget.HTMLElement

    def clear(self):
        self._filter_widgets = []
        super(WidgetPluginManager, self).clear()

    def get_widgets(self, file=None, place=None):
        return list(self.iter_widgets(file, place))

    def iter_widgets(self, file=None, place=None):
        for filter, endpoint, cwidget in self._filter_widgets:
            try:
                check = filter(file) if filter else True
            except BaseException as e:
                # Exception is handled  as this method execution is deffered,
                # making hard to debug for plugin developers.
                warnings.warn(
                    'Plugin action filtering failed with error: %s' % e,
                    RuntimeWarning
                    )
                continue
            if check and (place is None or place == cwidget.place):
                yield self.widget_class(endpoint, cwidget)

    def register_widget(self, widget, **kwargs):
        self.register_action(None, widget, **kwargs)

    def register_action(self, endpoint, widget, filter=None, **kwargs):
        self._filter_widgets.append((filter, endpoint, widget))


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
