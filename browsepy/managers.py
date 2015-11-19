
import sys

class MimetypeAction(object):
    def __init__(self, handler, endpoint, text):
        self.endpoint = endpoint
        self.handler = handler
        self.text = text


class MimetypeActionManager(object):
    action_class = MimetypeAction

    def __init__(self, app=None):
        self.root = {}
        if not app is None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app

        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['mimetype_action_manager'] = self

    def init_plugins(self, plugins):
        for plugin in plugins:
            self.load_plugin(plugin)

    def load_plugin(self, plugin):
        try:
            __import__(plugin)
        except ImportError:
            return
        module = sys.modules[plugin]
        if hasattr(module, 'load_actions'):
            module.load_actions(self.register)

    def add(self, mimetype, action):
        category, variant = mimetype.split('/')
        self.root.setdefault(category, {}).setdefault(variant, []).append(action)

    def get(self, mimetype):
        category, variant = mimetype.split('/')
        return [
            action
            for tree_category in (category, '*')
            for tree_variant in (variant, '*')
            for action in self.root.get(tree_category, {}).get(tree_variant, ())
        ]

    def register(self, url, text, mimetypes=(), **kwargs):
        def decorator(fnc):
            endpoint = kwargs.pop('endpoint', 'action_%s' % fnc.__name__)
            self.app.add_url_rule(
                rule=url,
                endpoint=endpoint,
                view_func=fnc,
                **kwargs)
            action = self.action_class(fnc, endpoint, text)
            for mimetype in mimetypes:
                self.add(mimetype, action)
            return fnc
        return decorator(kwargs.pop('view_func')) if 'view_func' in kwargs else decorator
