#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import os
import os.path
import argparse

from . import app


class ArgParse(argparse.ArgumentParser):
    def __init__(self):
        super(ArgParse, self).__init__(
            description = 'Web file browser'
        )
        cwd = os.path.abspath(os.getcwd())
        self.add_argument('host', nargs='?',
                          default=os.getenv('BROWSEPY_HOST', '127.0.0.1'),
                          help='address to listen (default: 127.0.0.1)')
        self.add_argument('port', nargs='?', type=int,
                          default=os.getenv('BROWSEPY_PORT', '8080'),
                          help='port to listen (default: 8080)')
        self.add_argument('--directory', metavar='PATH', type=self._directory,
                          default=cwd,
                          help='base serving directory (default: current path)')
        self.add_argument('--initial', metavar='PATH', type=self._directory,
                          help='initial directory (default: same as --directory)')
        self.add_argument('--removable', metavar='PATH', type=self._directory,
                          default=None,
                          help='base directory for remove (default: none)')
        self.add_argument('--upload', metavar='PATH', type=self._directory,
                          default=None,
                          help='base directory for upload (default: none)')
        self.add_argument('--plugin', metavar='PLUGIN_LIST', type=self._plugins,
                          default=[],
                          help='comma-separated list of plugins')
        self.add_argument('--debug', action='store_true', help='debug mode')

    def _plugins(self, arg):
        if not arg:
            return []
        return arg.split(',')

    def _directory(self, arg):
        if not arg:
            return None
        if os.path.isdir(arg):
            return os.path.abspath(arg)
        self.error('%s is not a valid directory' % arg)

if __name__ == '__main__':
    args = ArgParse().parse_args(sys.argv[1:])
    app.debug = args.debug
    app.config.update(
        directory_base = args.directory,
        directory_start = args.initial or args.directory,
        directory_remove = args.removable,
        directory_upload = args.upload,
        plugin_modules = args.plugin
        )
    app.run(host=os.getenv('BROWSEPY_HOST', args.host), port=args.port)
