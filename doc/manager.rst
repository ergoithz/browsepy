Manager Module
==============

.. currentmodule:: browsepy.manager

The browsepy's :doc:`manager` module centralizes all plugin-related
logic, hook calls and component registration methods.

For an extended explanation head over :doc:`plugins`.

Argument Plugin Manager
-----------------------

This class represents a subset of :class:`PluginManager` functionality, and
an instance of this class will be passed to :func:`register_arguments` plugin
module-level functions.

.. autoclass:: ArgumentPluginManager
  :members:
  :inherited-members:
  :undoc-members:

Plugin Manager
--------------

This class includes are the plugin registration functionality, and itself
will be passed to :func:`register_plugin` plugin module-level functions.

.. autoclass:: PluginManager
  :members:
  :inherited-members:
  :undoc-members:

Utility functions
-----------------

.. autofunction:: defaultsnamedtuple
