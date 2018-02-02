#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import os
import os.path
import argparse
import warnings

import flask

from . import app
from . import __meta__ as meta
from .compat import PY_LEGACY, getdebug, get_terminal_size
from .transform.glob import translate


class HelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog, indent_increment=2, max_help_position=24,
                 width=None):
        if width is None:
            try:
                width = get_terminal_size().columns - 2
            except ValueError:  # https://bugs.python.org/issue24966
                pass
        super(HelpFormatter, self).__init__(
            prog, indent_increment, max_help_position, width)


class PluginAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        warned = '%s_warning' % self.dest
        if ',' in value and not getattr(namespace, warned, False):
            setattr(namespace, warned, True)
            warnings.warn(
                'Comma-separated --plugin value is deprecated, '
                'use multiple --plugin options instead.'
                )
        values = value.split(',')
        prev = getattr(namespace, self.dest, None)
        if isinstance(prev, list):
            values = prev + [p for p in values if p not in prev]
        setattr(namespace, self.dest, values)


class ArgParse(argparse.ArgumentParser):
    default_directory = app.config['DIRECTORY_BASE']
    default_initial = (
        None
        if app.config['DIRECTORY_START'] == app.config['DIRECTORY_BASE'] else
        app.config['DIRECTORY_START']
        )
    default_removable = app.config['DIRECTORY_REMOVE']
    default_upload = app.config['DIRECTORY_UPLOAD']

    default_host = os.getenv('BROWSEPY_HOST', '127.0.0.1')
    default_port = os.getenv('BROWSEPY_PORT', '8080')
    plugin_action_class = PluginAction

    defaults = {
        'prog': meta.app,
        'formatter_class': HelpFormatter,
        'description': 'description: starts a %s web file browser' % meta.app
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
            '--plugin', metavar='MODULE',
            action=self.plugin_action_class,
            default=[],
            help='load plugin module (multiple)')
        self.add_argument(
            '--debug', action='store_true',
            help=argparse.SUPPRESS)

    def _path(self, arg):
        if PY_LEGACY and hasattr(sys.stdin, 'encoding'):
            encoding = sys.stdin.encoding or sys.getdefaultencoding()
            arg = arg.decode(encoding)
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
        exclude_fnc=filter_union(
            app.config['exclude_fnc'],
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
