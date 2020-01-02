#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import os
import os.path
import argparse

import flask

from . import app, __version__
from .compat import getdebug, SafeArgumentParser, HelpFormatter
from .transform.glob import translate


class CommaSeparatedAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        values = value.split(',')
        prev = getattr(namespace, self.dest, None)
        if isinstance(prev, list):
            values = prev + [p for p in values if p not in prev]
        setattr(namespace, self.dest, values)


class ArgParse(SafeArgumentParser):
    default_directory = app.config['DIRECTORY_BASE']
    default_initial = (
        None
        if app.config['DIRECTORY_START'] == app.config['DIRECTORY_BASE'] else
        app.config['DIRECTORY_START']
        )
    default_removable = app.config['DIRECTORY_REMOVE']
    default_upload = app.config['DIRECTORY_UPLOAD']
    name = app.config['APPLICATION_NAME']

    default_host = os.getenv('BROWSEPY_HOST', '127.0.0.1')
    default_port = os.getenv('BROWSEPY_PORT', '8080')

    defaults = {
        'prog': name,
        'formatter_class': HelpFormatter,
        'description': 'description: starts a %s web file browser' % name
        }

    def __init__(self, sep=os.sep):
        super(ArgParse, self).__init__(**self.defaults)
        self.add_argument(
            'host', nargs='?',
            default=self.default_host,
            help='address to listen (default: %(default)s)')
        self.add_argument(
            'port', nargs='?', type=int,
            default=self.default_port,
            help='port to listen (default: %(default)s)')
        self.add_argument(
            '--help', action='store_true',
            help='show help and exit (honors --plugin)')
        self.add_argument(
            '--help-all', action='store_true',
            help='show help for all available plugins and exit')
        self.add_argument(
            '--directory', metavar='PATH', type=self._directory,
            default=self.default_directory,
            help='serving directory (default: %(default)s)')
        self.add_argument(
            '--initial', metavar='PATH',
            type=lambda x: self._directory(x) if x else None,
            default=self.default_initial,
            help='default directory (default: same as --directory)')
        self.add_argument(
            '--removable', metavar='PATH', type=self._directory,
            default=self.default_removable,
            help='base directory allowing remove (default: %(default)s)')
        self.add_argument(
            '--upload', metavar='PATH', type=self._directory,
            default=self.default_upload,
            help='base directory allowing upload (default: %(default)s)')
        self.add_argument(
            '--exclude', metavar='PATTERN',
            action='append',
            default=[],
            help='exclude paths by pattern (multiple)')
        self.add_argument(
            '--exclude-from', metavar='PATH', type=self._file,
            action='append',
            default=[],
            help='exclude paths by pattern file (multiple)')
        self.add_argument(
            '--version', action='version',
            version=__version__)
        self.add_argument(
            '--plugin', metavar='MODULE',
            action=CommaSeparatedAction,
            default=[],
            help='load plugin module (multiple)')
        self.add_argument(
            '--debug', action='store_true',
            help=argparse.SUPPRESS)

    def _path(self, arg):
        return os.path.abspath(arg)

    def _file(self, arg):
        path = self._path(arg)
        if os.path.isfile(path):
            return path
        self.error('%s is not a valid file' % arg)

    def _directory(self, arg):
        path = self._path(arg)
        if os.path.isdir(path):
            return path
        self.error('%s is not a valid directory' % arg)


def create_exclude_fnc(patterns, base, sep=os.sep):
    if patterns:
        regex = '|'.join(translate(pattern, sep, base) for pattern in patterns)
        return re.compile(regex).search
    return None


def collect_exclude_patterns(paths):
    patterns = []
    for path in paths:
        with open(path, 'r') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if line:
                    patterns.append(line)
    return patterns


def list_union(*lists):
    lst = [i for l in lists for i in l]
    return sorted(frozenset(lst), key=lst.index)


def filter_union(*functions):
    filtered = [fnc for fnc in functions if fnc]
    if filtered:
        if len(filtered) == 1:
            return filtered[0]
        return lambda data: any(fnc(data) for fnc in filtered)
    return None


def main(argv=sys.argv[1:], app=app, parser=ArgParse, run_fnc=flask.Flask.run):
    plugin_manager = app.extensions['plugin_manager']
    args = plugin_manager.load_arguments(argv, parser())
    patterns = args.exclude + collect_exclude_patterns(args.exclude_from)
    if args.debug:
        os.environ['DEBUG'] = 'true'
    app.config.update(
        DIRECTORY_BASE=args.directory,
        DIRECTORY_START=args.initial or args.directory,
        DIRECTORY_REMOVE=args.removable,
        DIRECTORY_UPLOAD=args.upload,
        PLUGIN_MODULES=list_union(
            app.config['PLUGIN_MODULES'],
            args.plugin,
            ),
        EXCLUDE_FNC=filter_union(
            app.config['EXCLUDE_FNC'],
            create_exclude_fnc(patterns, args.directory),
            ),
        )
    plugin_manager.reload()
    run_fnc(
        app,
        host=args.host,
        port=args.port,
        debug=getdebug(),
        use_reloader=False,
        threaded=True
        )


if __name__ == '__main__':  # pragma: no cover
    main()
