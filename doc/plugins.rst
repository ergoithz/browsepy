Implementing plugins
====================

.. currentmodule:: browsepy.manager

browsepy is extensible via its powerful plugin API. Any plugin can

Protocol
--------

The plugin manager subsystem expects a `register_plugin` callable at module
level (in your __init__ module globals) which will be called with the manager
itself (type :class:`PluginManager`) as first parameter.

Plugin manager exposes several methods to register widgets and mimetype
detection functions.

A common `register_plugin` widget looks like (taken from player plugin):

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

A simple `register_arguments` example (from by player plugin):

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

Widgets
-------

Widget registration is provided by :meth:`PluginManager.register_widget`.

You can alternatively pass a widget object, via `widget` keyword argument, or use a pure functional approach by passing `place`, `type` and widget-specific
properties as keyword arguments.

In addition to that, you can define in which cases widget will be shown passing
a callable to `filter` argument keyword, which will receive a
:class:`browsepy.file.Node` (commonly a :class:`browsepy.file.File` or a
:class:`browsepy.file.Directory`) instance.

For those wanting the object-oriented approach, and for reference for those
wanting to know widget properties for using the functional way,
:attr:`WidgetPluginManager.widget_types` dictionary is
available.


Here is the "widget_types" for referrence.

.. code-block:: python

  class WidgetPluginManager(RegistrablePluginManager):
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

Function defaultsnamedtuple is just a namedtuple filling non-defined properties
with values taken from a dictionary passed as third constructor's argument or
None.

So keep in mind place and type are always required (otherwise widget won't be
drawn), and this properties are mutually excluyent:

* **link**: href superseedes endpoint.
* **button**: href superseedes endpoint.
* **upload**: action superseedes endpoint.
* **stylesheet**: href superseedes endpoint and filename
* **script**: src superseedes endpoint and filename.

Endpoints are Flask endpoint names, and endpoint handler functions must receive
a "filename" parameter for stylesheet and script widgets (allowing it to point
using with Flask's statics view) and a "path" argument for other cases. In the
former case it is recommended to use
:meth:`browsepy.file.Node.from_urlpath` static method to create the
appropriate file/directory object (see :mod:`browsepy.file`).

Considerations
--------------

When developing plugins, implementors should always choose the less intrusive
approach, so new browsepy versions will not likely get broken. That's why
stuff like :meth:`PluginManager.register_blueprint` is
provided and its usage is preferred over directly registering blueprints
via plugin manager's app reference (or even module-level app reference).

Said that, feel free to hack everything you want. Pull requests are definitely
welcome.
