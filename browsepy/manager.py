#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import collections
import argparse
import warnings

from . import mimetype
from . import widget
from .compat import isnonstriterable


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


class ActionPluginManager(RegistrablePluginManager):
    action_class = collections.namedtuple(
        'CallbackAction', ('endpoint', 'widget'))
    button_class = widget.ButtonWidget
    style_class = widget.StyleWidget
    javascript_class = widget.JavascriptWidget
    link_class = widget.LinkWidget

    def clear(self):
        self._action_widgets = {}
        self._action_callback = []
        super(ActionPluginManager, self).clear()

    def get_actions(self, file):
        return list(self.iter_actions(file))

    def iter_actions(self, file):
        for callback, endpoint, cwidget in self._action_callback:
            try:
                check = callback(file)
            except BaseException as e:
                # Exception is handled  as this method execution is deffered,
                # making hard to debug for plugin developers.
                warnings.warn(
                    'Plugin action filtering failed with error: %s' % e,
                    RuntimeWarning
                    )
            else:
                if check:
                    yield self.action_class(endpoint, cwidget.for_file(file))

    def get_widgets(self, place):
        return self._action_widgets.get(place, [])

    def register_widget(self, widget):
        self._action_widgets.setdefault(widget.place, []).append(widget)

    def register_action(self, endpoint, widget, callback=None, **kwargs):
        if callable(callback):
            self._action_callback.append((callback, endpoint, widget))


class MimetypeActionPluginManager(ActionPluginManager):
    action_class = collections.namedtuple(
        'MimetypeAction', ('endpoint', 'widget'))

    _default_mimetype_functions = (
        mimetype.by_python,
        mimetype.by_file,
        mimetype.by_default,
    )

    def clear(self):
        self._mimetype_root = {}  # mimetype tree root node
        self._mimetype_functions = list(self._default_mimetype_functions)
        super(MimetypeActionPluginManager, self).clear()

    def get_mimetype(self, path):
        for fnc in self._mimetype_functions:
            mime = fnc(path)
            if mime:
                return mime
        return mimetype.by_default(path)

    def iter_actions(self, file):
        for action in super(MimetypeActionPluginManager, self)\
                        .iter_actions(file):
            yield action

        category, variant = file.mimetype.split('/')
        for tree_category in (category, '*'):
            for tree_variant in (variant, '*'):
                acts = self._mimetype_root\
                    .get(tree_category, {})\
                    .get(tree_variant, ())
                for endpoint, cwidget in acts:
                    yield self.action_class(endpoint, cwidget.for_file(file))

    def register_mimetype_function(self, fnc):
        self._mimetype_functions.insert(0, fnc)

    def register_action(self, endpoint, widget, mimetypes=(), **kwargs):
        if not mimetypes:
            super(MimetypeActionPluginManager, self)\
                    .register_action(endpoint, widget, **kwargs)
            return
        mimetypes = mimetypes if isnonstriterable(mimetypes) else (mimetypes,)
        action = (endpoint, widget)
        for mime in mimetypes:
            category, variant = mime.split('/')
            self._mimetype_root.setdefault(
                category, {}
                ).setdefault(variant, []).append(action)


class ArgumentPluginManager(PluginManagerBase):
    _argparse_kwargs = {'add_help': False}
    _argparse_arguments = argparse.Namespace()

    def load_arguments(self, argv, base):
        parser = argparse.ArgumentParser(
            parents=(base,),
            add_help=False
            )
        for plugin in base.parse_known_args(argv)[0].plugin:
            module = self.import_plugin(plugin)
            if hasattr(module, 'register_arguments'):
                module.register_arguments(self)
        for argargs, argkwargs in self._argparse_argkwargs:
            parser.add_argument(*argargs, **argkwargs)
        self._argparse_arguments = parser.parse_args(argv)
        return self._argparse_arguments

    def clear(self):
        self._argparse_argkwargs = []
        super(ArgumentPluginManager, self).clear()

    def register_argument(self, *args, **kwargs):
        self._argparse_argkwargs.append((args, kwargs))

    def get_argument(self, name, default=None):
        return getattr(self._argparse_arguments, name, default)


class PluginManager(BlueprintPluginManager, MimetypeActionPluginManager,
                    ArgumentPluginManager):
    pass
