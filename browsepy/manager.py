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
        if app is not None:
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
            except (ImportError, KeyError):
                pass

        raise PluginNotFoundError(
            'No plugin module %r found, tried %r' % (plugin, names),
            plugin, names)


class BlueprintPluginManager(PluginManagerBase):
    def register_blueprint(self, blueprint):
        self.app.register_blueprint(blueprint)

    def load_plugin(self, plugin):
        module = super(BlueprintPluginManager, self).load_plugin(plugin)
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)
        return module


class ActionPluginManager(PluginManagerBase):
    action_class = collections.namedtuple(
        'CallbackAction', ('endpoint', 'widget'))
    button_class = widget.ButtonWidget
    style_class = widget.StyleWidget
    javascript_class = widget.JavascriptWidget
    link_class = widget.LinkWidget

    def __init__(self, app=None):
        self._widgets = {}
        self._callback_actions = []
        super(ActionPluginManager, self).__init__(app=app)

    def get_actions(self, file):
        return list(self.iter_actions(file))

    def iter_actions(self, file):
        for callback, endpoint, cwidget in self._callback_actions:
            if callback(file):
                yield self.action_class(endpoint, cwidget.for_file(file))

    def get_widgets(self, place):
        return self._widgets.get(place, [])

    def register_widget(self, widget):
        self._widgets.setdefault(widget.place, []).append(widget)

    def register_action(self, endpoint, widget, callback=None, **kwargs):
        if callable(callback):
            self._callback_actions.append((callback, endpoint, widget))


class MimetypeActionPluginManager(ActionPluginManager):
    action_class = collections.namedtuple(
        'MimetypeAction', ('endpoint', 'widget'))

    _default_mimetype_functions = [
        mimetype.by_python,
        mimetype.by_file,
        mimetype.by_default,
    ]

    def __init__(self, app=None):
        self._root = {}
        self._mimetype_functions = list(self._default_mimetype_functions)
        super(MimetypeActionPluginManager, self).__init__(app=app)

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
                acts = self._root.get(tree_category, {}).get(tree_variant, ())
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
            self._root.setdefault(
                category, {}
                ).setdefault(variant, []).append(action)


class PluginManager(BlueprintPluginManager, MimetypeActionPluginManager):
    pass
