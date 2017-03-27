#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import os.path
import argparse
import fnmatch
import re
import flask
import warnings
import collections

from . import app, compat
from .compat import PY_LEGACY


class ArgParse(argparse.ArgumentParser):
    default_directory = os.path.abspath(compat.getcwd())
    default_host = os.getenv('BROWSEPY_HOST', '127.0.0.1')
    default_port = os.getenv('BROWSEPY_PORT', '8080')
    pattern_class = collections.namedtuple(
        'Pattern', ('original', 'regex', 'deep', 'rooted')
        )

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
            '--exclude', metavar='PATTERN', type=self._pattern,
            action='append',
            default=[],
            help='exclude paths by pattern (multiple allowed)')
        self.add_argument(
            '--plugin', metavar='MODULE',
            action='append',
            default=[],
            help='load plugin module (multiple allowed)')
        self.add_argument('--debug', action='store_true', help='debug mode')

    def _pattern(self, arg):
        deep = '**' in arg
        rooted = arg.startswith('/')
        return self.pattern_class(arg, fnmatch.translate(arg), deep, rooted)

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
    plugins = args.plugin[:]
    if args.plugin and any(',' in plugin for plugin in args.plugin):
        warnings.warn(
            'Comma-separated --plugin value is deprecated, '
            'use multiple --plugin instead.'
            )
        added = 0
        for n, plugin in enumerate(plugins[:]):
            if ',' in plugin:
                multi = plugin.split(',')
                plugins[n + added:n + added + 1] = multi
                added += len(multi) - 1
    os.environ['DEBUG'] = 'true' if args.debug else ''
    app.config.update(
        directory_base=args.directory,
        directory_start=args.initial or args.directory,
        directory_remove=args.removable,
        directory_upload=args.upload,
        plugin_modules=plugins
        )
    if args.exclude:
        redeep = re.compile(
            '|'.join(i.regex for i in args.exclude if i.deep)
            ).match
        reflat = re.compile(
            '{sep}({pattern})'.format(
                sep=re.escape(os.sep),
                pattern='|'.join(i.regex for i in args.exclude if not i.deep)
                )
            ).search
        app.config['exclude_fnc'] = lambda path: redeep(path) or reflat(path)
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
