#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import collections

from . import mimetype
from . import widget
from .compat import isnonstriterable


class PluginNotFoundError(ImportError):
    pass


class PluginManagerBase(object):

    @property
    def namespaces(self):
        return self.app.config['plugin_namespaces']

    def __init__(self, app=None):
        if not app is None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['plugin_manager'] = self
        self.reload()

    def reload(self):
        for plugin in self.app.config.get('plugin_modules', ()):
            self.load_plugin(plugin)

    def load_plugin(self, plugin):
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
            except (ImportError, IndexError):
                pass

        raise PluginNotFoundError('No plugin module %r found, tried %r' % (plugin, names), plugin, names)


class BlueprintPluginManager(PluginManagerBase):
    def register_blueprint(self, blueprint):
        self.app.register_blueprint(blueprint)

    def load_plugin(self, plugin):
        module = super(BlueprintPluginManager, self).load_plugin(plugin)
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)
        return module


class MimetypeActionPluginManager(PluginManagerBase):
    action_class = collections.namedtuple('MimetypeAction', ('endpoint', 'widget'))
    button_class = widget.ButtonWidget
    style_class = widget.StyleWidget
    javascript_class = widget.JavascriptWidget

    def __init__(self, app=None):
        self._root = {}
        self._widgets = {}
        self._mimetype_functions = [
            mimetype.by_default,
            mimetype.by_file,
            mimetype.by_python
        ]
        super(MimetypeActionPluginManager, self).__init__(app=app)

    def get_mimetype(self, path):
        for fnc in reversed(self._mimetype_functions):
            mime = fnc(path)
            if mime:
                return mime
        return mimetype.by_default(path)

    def get_widgets(self, place):
        return self._widgets.get(place, [])

    def get_actions(self, mimetype):
        category, variant = mimetype.split('/')
        return [
            action
            for tree_category in (category, '*')
            for tree_variant in (variant, '*')
            for action in self._root.get(tree_category, {}).get(tree_variant, ())
            ]

    def register_mimetype_function(self, fnc):
        self._mimetype_functions.append(fnc)

    def register_widget(self, widget):
        self._widgets.setdefault(widget.place, []).append(widget)

    def register_action(self, endpoint, widget, mimetypes=(), **kwargs):
        mimetypes = mimetypes if isnonstriterable(mimetypes) else (mimetypes,)
        action = self.action_class(endpoint, widget)
        for mimetype in mimetypes:
            category, variant = mimetype.split('/')
            self._root.setdefault(category, {}).setdefault(variant, []).append(action)


class PluginManager(BlueprintPluginManager, MimetypeActionPluginManager):
    pass
