.. browsepy documentation master file, created by
   sphinx-quickstart on Thu Nov 17 11:54:15 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to browsepy's documentation!
====================================

Welcome to browsepy's documentation. It's recommended to start reading both
:ref:`quickstart` and, specifically :ref:`quickstart-installation`, while more
detailed tutorials about integrating :mod:`browsepy` as module or plugin
development are also available.

Browsepy has few dependencies: `Flask`_ and `Scandir`_. `Flask`_ is an awesome
web microframework while `Scandir`_ is a directory listing library which `was
included <https://www.python.org/dev/peps/pep-0471/>`_ in Python 3.5's
standard library.

If you want to dive into their documentation, check out the following links:

* `Flask Documentation
  <http://flask.pocoo.org/docs/>`_
* `Scandir Readme
  <https://github.com/benhoyt/scandir/blob/master/README.rst>`_
* `Scandir Python Documentation
  <https://docs.python.org/3.5/library/os.html#os.scandir>`_

.. _Flask: http://jinja.pocoo.org/
.. _Scandir: http://werkzeug.pocoo.org/

User's Guide
============
Instructions for users, implementers and developers.

.. toctree::
   :maxdepth: 2

   quickstart
   exclude
   builtin_plugins
   plugins
   integrations

API Reference
=============
Specific information about functions, class or methods.

.. toctree::
   :maxdepth: 2

   manager
   file
   stream
   compat
   tests_utils

Indices and tables
==================
Random documentation content references.

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
