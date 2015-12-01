#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import collections

from markupsafe import Markup
from flask import url_for

from . import mimetype
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

    def import_plugin(self, plugin):
        names = [
            '%s.%s' % (namespace, plugin) if namespace else plugin
            for namespace in self.namespaces
            ]
        for name in names:
            try:
                __import__(name)
                return sys.modules[name]
            except (ImportError, IndexError):
                pass
        raise PluginNotFoundError('No plugin module %r found, tried %r' % (plugin, names), plugin, names)

    def load_plugin(self, plugin):
        module = self.import_plugin(plugin)
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)
        return module


class BlueprintPluginManager(PluginManagerBase):
    def register_blueprint(self, blueprint):
        self.app.register_blueprint(blueprint)


class WidgetBase(object):
    place = None
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class ButtonWidget(WidgetBase):
    place = 'button'
    def __init__(self, html='', text='', css=""):
        self.content = Markup(html) if html else text
        self.css = css


class StyleWidget(WidgetBase):
    place = 'style'

    @property
    def href(self):
        return url_for(*self.args, **self.kwargs)

class JavascriptWidget(WidgetBase):
    place = 'javascript'

    @property
    def src(self):
        return url_for(*self.args, **self.kwargs)


class MimetypeActionPluginManager(PluginManagerBase):
    action_class = collections.namedtuple('MimetypeAction', ('endpoint', 'widget'))
    button_class = ButtonWidget
    style_class = StyleWidget
    javascript_class = JavascriptWidget

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
            mimetype = fnc(path)
            if mimetype:
                return mimetype
        return mimetype_by_default(path)

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
