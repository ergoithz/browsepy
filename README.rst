browsepy
========

.. image:: http://img.shields.io/travis/ergoithz/browsepy/master.svg?style=flat-square
  :target: https://travis-ci.org/ergoithz/browsepy
  :alt: Travis-CI badge

.. image:: https://img.shields.io/appveyor/ci/ergoithz/browsepy/master.svg?style=flat-square
  :target: https://ci.appveyor.com/project/ergoithz/browsepy/branch/master
  :alt: AppVeyor badge

.. image:: http://img.shields.io/coveralls/ergoithz/browsepy/master.svg?style=flat-square
  :target: https://coveralls.io/r/ergoithz/browsepy?branch=master
  :alt: Coveralls badge

.. image:: https://img.shields.io/codacy/grade/e27821fb6289410b8f58338c7e0bc686/master.svg?style=flat-square
  :target: https://www.codacy.com/app/ergoithz/browsepy/dashboard?bid=4246124
  :alt: Codacy badge

.. image:: http://img.shields.io/pypi/l/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: License: MIT

.. image:: http://img.shields.io/pypi/v/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Version: 0.5.6

.. image:: https://img.shields.io/badge/python-2.7%2B%2C%203.3%2B-FFC100.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Python 2.7+, 3.3+

The simple web file browser.

Documentation
-------------

Head to http://ergoithz.github.io/browsepy/ for an online version of current
*master* documentation,

You can also build yourself from sphinx sources using the documentation
`Makefile` located at `docs` directory.

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
* Player plugin is now able to load `m3u` and `pls` playlists, and optionally
  play everything on a directory (adding a command-line argument).
* Browsing now takes full advantage of `scandir` (already in Python 3.5 and an
  external dependency for older versions) providing faster directory listing.
* Custom file ordering while browsing directories.
* Easy multi-file uploads.
* Jinja2 template output minification, saving those precious bytes.
* Setup script now registers a proper `browsepy` command.

Install
-------

*Note*: with some legacy Python versions shiping outdated libraries, both
`pip` and `setuptools` library should be upgraded with
`pip install --upgrade pip setuptools`.

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

Showing help all detected plugin arguments

.. code-block:: bash

  browsepy --help-all

This examples assume python's `bin` directory is in `PATH`, otherwise try
replacing `browsepy` with `python -m browsepy`.

Command-line arguments
----------------------

This is what is printed when you run `browsepy --help`, keep in mind that
plugins (loaded with `plugin` argument) could add extra arguments to this list.

::

  usage: browsepy [-h] [--help-all] [--directory PATH] [--initial PATH] [--removable PATH] [--upload PATH] [--exclude PATTERN]
                  [--exclude-from PATH] [--version] [--plugin MODULE]
                  [host] [port]

  description: starts a browsepy web file browser

  positional arguments:
    host                 address to listen (default: 127.0.0.1)
    port                 port to listen (default: 8080)

  optional arguments:
    -h, --help           show this help message and exit
    --help-all           show help for all available plugins and exit
    --directory PATH     serving directory (default: /home/work/Desarrollo/browsepy)
    --initial PATH       default directory (default: same as --directory)
    --removable PATH     base directory allowing remove (default: None)
    --upload PATH        base directory allowing upload (default: None)
    --exclude PATTERN    exclude paths by pattern (multiple)
    --exclude-from PATH  exclude paths by pattern file (multiple)
    --version            show program's version number and exit
    --plugin MODULE      load plugin module (multiple)

  available plugins:
    file-actions, browsepy.plugin.file_actions
    player, browsepy.plugin.player


Using as library
----------------

It's a python module, so you can import **browsepy**, mount **app**, and serve
it (it's `WSGI`_ compliant) using
your preferred server.

Browsepy is a Flask application, so it can be served along with any `WSGI`_ app
just setting **APPLICATION_ROOT** in **browsepy.app** config to browsepy prefix
url, and mounting **browsepy.app** on the appropriate parent
*url-resolver*/*router*.

.. _WSGI: https://www.python.org/dev/peps/pep-0333/

Browsepy app config (available at :attr:`browsepy.app.config`) uses the
following configuration options.

* **DIRECTORY_BASE**: anything under this directory will be served,
  defaults to current path.
* **DIRECTORY_START**: directory will be served when accessing root URL
* **DIRECTORY_REMOVE**: file removing will be available under this path,
  defaults to **None**.
* **DIRECTORY_UPLOAD**: file upload will be available under this path,
  defaults to **None**.
* **DIRECTORY_TAR_BUFFSIZE**, directory tar streaming buffer size,
  defaults to **262144** and must be multiple of 512.
* **DIRECTORY_DOWNLOADABLE** whether enable directory download or not,
  defaults to **True**.
* **USE_BINARY_MULTIPLES** whether use binary units (bi-bytes, like KiB)
  instead of common ones (bytes, like KB), defaults to **True**.
* **PLUGIN_MODULES** list of module names (absolute or relative to
  plugin_namespaces) will be loaded.
* **PLUGIN_NAMESPACES** prefixes for module names listed at PLUGIN_MODULES
  where relative PLUGIN_MODULES are searched.
* **EXCLUDE_FNC** function will be used to exclude files from listing and
  directory tarballs. Can be either None or function receiving an absolute
  path and returning a boolean.

After editing `PLUGIN_MODULES` value, plugin manager (available at module
plugin_manager and app.extensions['plugin_manager']) should be reloaded using
the `reload` method.

The other way of loading a plugin programmatically is calling plugin manager's
`load_plugin` method.

Extend via plugin API
---------------------

Starting from version 0.4.0, browsepy is extensible via plugins. A functional
'player' plugin is provided as example, and some more are planned.

Starting from version 0.6.0, browsepy a new plugin `file-actions` is included
providing copy/cut/paste and directory creation operations.

Plugins can add HTML content to browsepy's browsing view, using some
convenience abstraction for already used elements like external stylesheet and
javascript tags, links, buttons and file upload.

More information at http://ergoithz.github.io/browsepy/plugins.html
