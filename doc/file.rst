File Module
===========

.. currentmodule:: browsepy.file

For more advanced use-cases dealing with the filesystem, the browsepy's own
classes (`Node`, `File` and `Directory`) can be used (or inherited).

:class:`Node` is meant for implementing your own special filesystem nodes, via
inheritance (it's abstract so shouldn't be instantiated directly). Just
remember to overload its :attr:`Node.generic` attribute value to False.

Both :class:`File` :class:`Directory` can be used as is or implementing, via
inheritance, extra logic like different default widgets, virtual data (see
player plugin).


.. automodule:: browsepy.file
  :members:
  :undoc-members:
