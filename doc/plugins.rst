.. _plugins:

Plugin Development
==================

.. currentmodule:: browsepy.manager

browsepy is extensible via a powerful plugin API. A plugin can register
its own Flask blueprints, file browser widgets (filtering by file), mimetype
detection functions and even its own command line arguments.

A fully functional :mod:`browsepy.plugin.player` plugin module is provided as
example.

.. _plugins-namespace:

Plugin Namespace
----------------

Plugins are regular python modules. They are loaded by `--plugin`
:ref:`console argument <quickstart-usage>`.

Aiming to make plugin names shorter, browsepy try to load plugins
using namespaces
and prefixes defined on configuration's ``plugin_namespaces`` entry on
:attr:`browsepy.app.config`. Its default value is browsepy's built-in module namespace
`browsepy.plugins`, `browsepy_` prefix and an empty namespace (so any plugin could
be used with its full module name).

Summarizing, with default configuration:

* Any python module inside `browsepy.plugin` can be loaded as plugin by its
  relative module name, ie. ``player`` instead of ``browsepy.plugin.player``.
* Any python module prefixed by ``browsepy_`` can be loaded as plugin by its
  unprefixed name, ie. ``myplugin`` instead of ``browsepy_myplugin``.
* Any python module can be loaded as plugin by its full module name.

Said that, you can name your own plugin so it could be loaded easily.

.. _plugins-namespace-examples:

Examples
++++++++

Your built-in plugin, placed under `browsepy/plugins/` in your own
browsepy fork:

.. code-block:: bash

  browsepy --plugin=my_builtin_module

Your prefixed plugin, a regular python module in python's library path,
named `browsepy_prefixed_plugin`:

.. code-block:: bash

  browsepy --plugin=prefixed_plugin

Your plugin, a regular python module in python's library path, named `my_plugin`.

.. code-block:: bash

  browsepy --plugin=my_plugin

.. _plugins-protocol:

Protocol
--------

The plugin manager subsystem expects a `register_plugin` callable at module
level (in your **__init__** module globals) which will be called with the
manager itself (type :class:`PluginManager`) as first parameter.

Plugin manager exposes several methods to register widgets and mimetype
detection functions.

A *sregister_plugin*s function looks like this (taken from player plugin):

.. code-block:: python

  def register_plugin(manager):
      '''
      Register blueprints and actions using given plugin manager.

      :param manager: plugin manager
      :type manager: browsepy.manager.PluginManager
      '''
      manager.register_blueprint(player)
      manager.register_mimetype_function(detect_playable_mimetype)

      # add style tag
      manager.register_widget(
          place='styles',
          type='stylesheet',
          endpoint='player.static',
          filename='css/browse.css'
      )

      # register link actions
      manager.register_widget(
          place='entry-link',
          type='link',
          endpoint='player.audio',
          filter=PlayableFile.detect
      )
      manager.register_widget(
          place='entry-link',
          icon='playlist',
          type='link',
          endpoint='player.playlist',
          filter=PlayListFile.detect
      )

      # register action buttons
      manager.register_widget(
          place='entry-actions',
          css='play',
          type='button',
          endpoint='player.audio',
          filter=PlayableFile.detect
      )
      manager.register_widget(
          place='entry-actions',
          css='play',
          type='button',
          endpoint='player.playlist',
          filter=PlayListFile.detect
      )

      # check argument (see `register_arguments`) before registering
      if manager.get_argument('player_directory_play'):
          # register header button
          manager.register_widget(
              place='header',
              type='button',
              endpoint='player.directory',
              text='Play directory',
              filter=PlayableDirectory.detect
              )

In case you need to add extra command-line-arguments to browsepy command,
:func:`register_arguments` method can be also declared (like register_plugin,
at your plugin's module level). It will receive a
:class:`ArgumentPluginManager` instance, providing an argument-related subset of whole plugin manager's functionality.

A simple `register_arguments` example (from player plugin):

.. code-block:: python

  def register_arguments(manager):
      '''
      Register arguments using given plugin manager.

      This method is called before `register_plugin`.

      :param manager: plugin manager
      :type manager: browsepy.manager.PluginManager
      '''

      # Arguments are forwarded to argparse:ArgumentParser.add_argument,
      # https://docs.python.org/3.7/library/argparse.html#the-add-argument-method
      manager.register_argument(
          '--player-directory-play', action='store_true',
          help='enable directories as playlist'
          )

.. _widgets:

Widgets
-------

Widget registration is provided by :meth:`PluginManager.register_widget`.

You can alternatively pass a widget object, via `widget` keyword
argument, or use a pure functional approach by passing `place`,
`type` and the widget-specific properties as keyword arguments.

In addition to that, you can also define in which cases widget will be shown passing
a callable to `filter` argument keyword, which will receive a
:class:`browsepy.file.Node` (commonly a :class:`browsepy.file.File` or a
:class:`browsepy.file.Directory`) instance.

For those wanting the object-oriented approach, and for reference for those
wanting to know widget properties for using the functional way,
:attr:`WidgetPluginManager.widget_types` dictionary is
available, containing widget namedtuples (see :func:`collections.namedtuple`) definitions.


Here is the "widget_types" for reference.

.. code-block:: python

  class WidgetPluginManager(RegistrablePluginManager):
      ''' ... '''
      widget_types = {
          'base': defaultsnamedtuple(
              'Widget',
              ('place', 'type')),
          'link': defaultsnamedtuple(
              'Link',
              ('place', 'type', 'css', 'icon', 'text', 'endpoint', 'href'),
              {
                  'text': lambda f: f.name,
                  'icon': lambda f: f.category
              }),
          'button': defaultsnamedtuple(
              'Button',
              ('place', 'type', 'css', 'text', 'endpoint', 'href')),
          'upload': defaultsnamedtuple(
              'Upload',
              ('place', 'type', 'css', 'text', 'endpoint', 'action')),
          'stylesheet': defaultsnamedtuple(
              'Stylesheet',
              ('place', 'type', 'endpoint', 'filename', 'href')),
          'script': defaultsnamedtuple(
              'Script',
              ('place', 'type', 'endpoint', 'filename', 'src')),
          'html': defaultsnamedtuple(
              'Html',
              ('place', 'type', 'html')),
      }

Function :func:`browsepy.file.defaultsnamedtuple` is a
:func:`collections.namedtuple` which uses a third argument dictionary
as default attribute values. None is assumed as implicit default.

All attribute values can be either :class:`str` or a callable accepting
a :class:`browsepy.file.Node` instance as argument and returning said :class:`str`,
allowing dynamic widget content and behavior.

Please note place and type are always required (otherwise widget won't be
drawn), and this properties are mutually exclusive:

* **link**: attribute href supersedes endpoint.
* **button**: attribute href supersedes endpoint.
* **upload**: attribute action supersedes endpoint.
* **stylesheet**: attribute href supersedes endpoint and filename
* **script**: attribute src supersedes endpoint and filename.

Endpoints are Flask endpoint names, and endpoint handler functions must receive
a "filename" parameter for stylesheet and script widgets (allowing it to point
using with Flask's statics view) and a "path" argument for other use-cases. In the
former case it is recommended to use
:meth:`browsepy.file.Node.from_urlpath` static method to create the
appropriate file/directory object (see :mod:`browsepy.file`).

.. _plugins-considerations:

Considerations
--------------

Name your plugin wisely, look at `pypi <https://pypi.python.org/>`_ for
conflicting module names.

Always choose the less intrusive approach on plugin development, so new
browsepy versions will not likely break it. That's why stuff like
:meth:`PluginManager.register_blueprint` is provided and its usage is
preferred over directly registering blueprints via plugin manager's app
reference (or even module-level app reference).

A good way to keep your plugin working on future browsepy releases is
:ref:`upstreaming it <builtin-plugins-contributing>` onto browsepy itself.

Feel free to hack everything you want. Pull requests are definitely welcome.
