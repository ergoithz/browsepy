.. _manager:

Manager Module
==============

.. currentmodule:: browsepy.manager

The browsepy's :doc:`manager` module centralizes all plugin-related
logic, hook calls and component registration methods.

For an extended explanation head over :doc:`plugins`.

.. _manager-argument:

Argument Plugin Manager
-----------------------

This class represents a subset of :class:`PluginManager` functionality, and
an instance of this class will be passed to :func:`register_arguments` plugin
module-level functions.

.. autoclass:: ArgumentPluginManager
  :members:
  :inherited-members:
  :undoc-members:

.. _manager-plugin:

Plugin Manager
--------------

This class includes are the plugin registration functionality, and itself
will be passed to :func:`register_plugin` plugin module-level functions.

.. autoclass:: PluginManager
  :members:
  :inherited-members:
  :undoc-members:
  :exclude-members: register_action, get_actions, action_class, style_class,
                    button_class, javascript_class, link_class, widget_types

  .. autoattribute:: widget_types

    Dictionary with widget type names and their corresponding class (based on
    namedtuple, see :func:`defaultsnamedtuple`) so it could be instanced and
    reused (see :meth:`register_widget`).

.. _manager-util:

Utility functions
-----------------

.. autofunction:: defaultsnamedtuple
