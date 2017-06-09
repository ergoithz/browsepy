.. _file:

File Module
===========

.. currentmodule:: browsepy.file

For more advanced use-cases dealing with the filesystem, the browsepy's own
classes (:class:`Node`, :class:`File` and :class:`Directory`) can be
instantiated and inherited.

:class:`Node` class is meant for implementing your own special filesystem
nodes, via inheritance (it's abstract so shouldn't be instantiated directly).
Just remember to overload its :attr:`Node.generic` attribute value to False.

Both :class:`File` and :class:`Directory` classes can be instantiated or
extended, via inheritance, with logic like different default widgets, virtual data (see player plugin code).

.. _file-node:

Node
----

.. currentmodule:: browsepy.file

.. autoclass:: Node
  :members:
  :inherited-members:
  :undoc-members:

.. _file-directory:

Directory
---------

.. autoclass:: Directory
  :show-inheritance:
  :members:
  :inherited-members:
  :undoc-members:

.. _file-file:

File
----

.. autoclass:: File
  :show-inheritance:
  :members:
  :inherited-members:
  :undoc-members:

.. _file-exceptions:

Exceptions
----------

.. autoclass:: OutsideDirectoryBase
  :show-inheritance:

.. autoclass:: OutsideRemovableBase
  :show-inheritance:

.. _file-util:

Utility functions
-----------------

.. autofunction:: fmt_size
.. autofunction:: abspath_to_urlpath
.. autofunction:: urlpath_to_abspath
.. autofunction:: check_under_base
.. autofunction:: check_base
.. autofunction:: check_path
.. autofunction:: secure_filename
.. autofunction:: alternative_filename
.. autofunction:: scandir
