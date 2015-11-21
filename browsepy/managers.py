#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import collections

from .__meta__ import __app__


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
        return self.import_plugin(plugin)


class BlueprintPluginManager(PluginManagerBase):
    def load_plugin(self, plugin):
        module = super(BlueprintPluginManager, self).load_plugin(plugin)
        if hasattr(module, 'load_blueprints'):
            module.load_blueprints(self)
        return module

    def register_blueprint(self, blueprint):
        self.app.register_blueprint(blueprint)


class MimetypeActionPluginManager(PluginManagerBase):
    action_class = collections.namedtuple('MimetypeAction', ('endpoint', 'text'))

    def __init__(self, app=None):
        self.root = {}
        super(MimetypeActionPluginManager, self).__init__(app=app)

    def load_plugin(self, plugin):
        module = super(MimetypeActionPluginManager, self).load_plugin(plugin)
        if hasattr(module, 'load_actions'):
            module.load_actions(self)
        return module

    def get_actions(self, mimetype):
        category, variant = mimetype.split('/')
        return [
            action
            for tree_category in (category, '*')
            for tree_variant in (variant, '*')
            for action in self.root.get(tree_category, {}).get(tree_variant, ())
            ]

    def register_action(self, endpoint, text, mimetypes=(), **kwargs):
        action = self.action_class(endpoint, text)
        for mimetype in mimetypes:
            category, variant = mimetype.split('/')
            self.root.setdefault(category, {}).setdefault(variant, []).append(action)


class PluginManager(BlueprintPluginManager, MimetypeActionPluginManager):
    pass
