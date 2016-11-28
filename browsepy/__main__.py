#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import os.path
import argparse
import flask

from . import app, compat
from .compat import PY_LEGACY


class ArgParse(argparse.ArgumentParser):
    default_directory = os.path.abspath(compat.getcwd())
    default_host = os.getenv('BROWSEPY_HOST', '127.0.0.1')
    default_port = os.getenv('BROWSEPY_PORT', '8080')

    description = 'extendable web file browser'

    def __init__(self):
        super(ArgParse, self).__init__(description=self.description)

        self.add_argument(
            'host', nargs='?',
            default=self.default_host,
            help='address to listen (default: %(default)s)')
        self.add_argument(
            'port', nargs='?', type=int,
            default=self.default_port,
            help='port to listen (default: %(default)s)')
        self.add_argument(
            '--directory', metavar='PATH', type=self._directory,
            default=self.default_directory,
            help='base serving directory (default: current path)')
        self.add_argument(
            '--initial', metavar='PATH', type=self._directory,
            help='initial directory (default: same as --directory)')
        self.add_argument(
            '--removable', metavar='PATH', type=self._directory,
            default=None,
            help='base directory for remove (default: none)')
        self.add_argument(
            '--upload', metavar='PATH', type=self._directory,
            default=None,
            help='base directory for upload (default: none)')
        self.add_argument(
            '--plugin', metavar='PLUGIN_LIST', type=self._plugin,
            default=[],
            help='comma-separated list of plugins')
        self.add_argument('--debug', action='store_true', help='debug mode')

    def _plugin(self, arg):
        return arg.split(',') if arg else []

    def _directory(self, arg):
        if not arg:
            return None
        if PY_LEGACY and hasattr(sys.stdin, 'encoding'):
            encoding = sys.stdin.encoding or sys.getdefaultencoding()
            arg = arg.decode(encoding)
        if os.path.isdir(arg):
            return os.path.abspath(arg)
        self.error('%s is not a valid directory' % arg)


def main(argv=sys.argv[1:], app=app, parser=ArgParse, run_fnc=flask.Flask.run):
    plugin_manager = app.extensions['plugin_manager']
    args = plugin_manager.load_arguments(argv, parser())
    os.environ['DEBUG'] = 'true' if args.debug else ''
    app.config.update(
        directory_base=args.directory,
        directory_start=args.initial or args.directory,
        directory_remove=args.removable,
        directory_upload=args.upload,
        plugin_modules=args.plugin
        )
    plugin_manager.reload()
    run_fnc(
        app,
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=False,
        threaded=True
        )


if __name__ == '__main__':
    main()
