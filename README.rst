browsepy
========

.. image:: http://img.shields.io/travis/ergoithz/browsepy/master.svg?style=flat-square
  :target: https://travis-ci.org/ergoithz/browsepy
  :alt: Build status

.. image:: http://img.shields.io/coveralls/ergoithz/browsepy/master.svg?style=flat-square
  :target: https://coveralls.io/r/ergoithz/browsepy
  :alt: Test coverage

.. image:: https://img.shields.io/scrutinizer/g/ergoithz/browsepy/master.svg?style=flat-square
  :target: https://scrutinizer-ci.com/g/ergoithz/browsepy/
  :alt: Code quality

.. image:: http://img.shields.io/pypi/l/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: License

.. image:: http://img.shields.io/pypi/v/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Latest Version

.. image:: http://img.shields.io/pypi/dm/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Downloads

.. image:: https://img.shields.io/badge/python-2.7%2B%2C%203.3%2B-FFC100.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Python 2.7+, 3.3+

The simple web file browser.

Documentation
-------------

Head to http://ergoithz.github.io/browsepy/ for an online version of current
*master* documentation,

You can also build yourself from sphinx sources using the documentation
Makefile at the docs folder.

Screenshots
-----------

.. image:: https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png
  :target: https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png
  :alt: Screenshot of directory with enabled remove

Features
--------

* **Simple**, like Python's SimpleHTTPServer or Apache's Directory Listing.
* **Downloadable directories**, streaming directory tarballs on the fly.
* **Optional remove** for files under given path.
* **Optional upload** for directories under given path.
* **Player** audio player plugin is provided (without transcoding).

New in 0.5
----------

* File and plugin APIs have been fully reworked making them more complete and
  extensible, so they can be considered stable now. As a side-effect backward
  compatibility on some edge cases could be broken (please fill an issue if
  your code is affected).

  * Old widget API have been deprecated and warnings will be shown if used.
  * Widget registration in a single call (passing a widget instances is still
    available though), no more action-widget duality.
  * Callable-based widget filtering (no longer limited to mimetypes).
  * A raw HTML widget for maximum flexibility.

* Plugins can register command-line arguments now.
* Player plugin is now able to load m3u and pls playlists, and optionally
  play everything on a directory (adding a command-line argument).
* Browsing now takes full advantage of scandir (already in Python 3.5 and an
  external dependecy for older versions) providing faster directory listing.
* Custom file ordering while browsing directories.
* Easy multi-file uploads.
* Jinja2 template output minification, saving those precious bytes.
* Setup script now registers a proper `browsepy` command.

Install
-------

It's on `pypi` so...

.. _pypi: https://pypi.python.org/pypi/browsepy/

.. code-block:: bash

   pip install browsepy


You can get the development version from our `github repository`.

.. _github repository: https://github.com/ergoithz/browsepy

.. code-block:: bash

   pip install git+https://github.com/ergoithz/browsepy.git


Usage
-----

Serving $HOME/shared to all addresses

.. code-block:: bash

   browsepy 0.0.0.0 8080 --directory $HOME/shared

Showing help

.. code-block:: bash

   browsepy --help

Showing help including player plugin arguments

.. code-block:: bash

  browsepy --plugin=player --help

This examples assume python's `bin` directory is in `PATH`, otherwise try
replacing `browsepy` with `python -m browsepy`.

Command-line arguments
----------------------

This is what is printed when you run `browsepy --help`, keep in mind that
plugins (loaded with `plugin` argument) could add extra arguments to this list.

::

    usage: browsepy [-h] [--directory PATH] [--initial PATH] [--removable PATH]
                    [--upload PATH] [--plugin PLUGIN_LIST] [--debug]
                    [host] [port]

    positional arguments:
      host                  address to listen (default: 127.0.0.1)
      port                  port to listen (default: 8080)

    optional arguments:
      -h, --help            show this help message and exit
      --directory PATH      base serving directory (default: current path)
      --initial PATH        initial directory (default: same as --directory)
      --removable PATH      base directory for remove (default: none)
      --upload PATH         base directory for upload (default: none)
      --plugin PLUGIN_LIST  comma-separated list of plugins
      --debug               debug mode

Using as library
----------------

It's a python module, so you can import **browsepy**, mount **app**, and serve
it (it's wsgi compliant) using your preferred server.

Browsepy is a Flask application, so it can be served along with any wsgi app
just setting **APPLICATION_ROOT** in **browsepy.app** config to browsepy prefix
url, and mounting **browsepy.app** on the appropriate parent
*url-resolver*/*router*.

Browsepy app config (available at browsepy.app.config) uses the following
configuration options.

* **directory_base**: anything under this directory will be served,
  defaults to current path.
* **directory_start**: directory will be served when accessing root url
* **directory_remove**: file removing will be available under this path,
  defaults to **None**.
* **directory_upload**: file upload will be available under this path,
  defaults to **None**.
* **directory_tar_buffsize**, directory tar streaming buffer size,
  defaults to **262144** and must be multiple of 512.
* **directory_downloadable** whether enable directory download or not,
  defaults to **True**.
* **use_binary_multiples** whether use binary units (bi-bytes, like KiB)
  instead of common ones (bytes, like KB), defaults to **True**.
* **plugin_modules** list of module names (absolute or relative to
  plugin_namespaces) will be loaded.
* **plugin_namespaces** prefixes for module names listed at plugin_modules
  where relative plugin_modules are searched.

After editing `plugin_modules` value, plugin manager (available at module
plugin_manager and app.extensions['plugin_manager']) should be reloaded using
the `reload` method.

The other way of loading a plugin programatically is calling plugin manager's
`load_plugin` method.

Extend via plugin API
---------------------

Starting from version 0.4.0, browsepy is extensible via plugins. A functional
'player' plugin is provided as example, and some more are planned.

Plugins can add html content to browsepy's browsing view, using some
convenience abstraction for already used elements like external stylesheet and
javascript tags, links, buttons and file upload.

The plugin manager will look for two callables on your module
`register_arguments` and `register_plugin`.
