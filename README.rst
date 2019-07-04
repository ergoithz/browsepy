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

.. image:: https://img.shields.io/badge/python-2.7%2B%2C%203.4%2B-FFC100.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Python 2.7+, 3.5+

The simple web file browser.

Documentation
-------------

Head to http://ergoithz.github.io/browsepy/ for an online version of current
*master* documentation,

You can also build yourself from sphinx sources using the documentation
`Makefile` located under `docs` directory.

License
-------

MIT. See `LICENSE`_.

.. _LICENSE: https://raw.githubusercontent.com/ergoithz/browsepy/master/LICENSE

Changelog
---------

See `CHANGELOG`_.

.. _CHANGELOG: https://raw.githubusercontent.com/ergoithz/browsepy/master/CHANGELOG

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
* **Plugins**
  * **player**, web audio player.
  * **file-actions**, cut, copy paste and directory creation.

Install
-------

*Note*: with some legacy Python versions shipping outdated libraries, both
`pip` and `setuptools` libraries should be upgraded with
`pip install --upgrade pip setuptools`.

It's on `pypi`_ so...

.. _pypi: https://pypi.python.org/pypi/browsepy/

.. code-block:: bash

   pip install browsepy


You can get the same version from our `github repository`_.

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
plugins (loaded with `plugin` argument) could add extra arguments to this list
(you can see all them running `browsepy --help-all` instead).

::

  usage: browsepy [-h] [--help-all] [--directory PATH] [--initial PATH]
                  [--removable PATH] [--upload PATH] [--exclude PATTERN]
                  [--exclude-from PATH] [--version] [--plugin MODULE]
                  [host] [port]

  description: starts a browsepy web file browser

  positional arguments:
    host                 address to listen (default: 127.0.0.1)
    port                 port to listen (default: 8080)

  optional arguments:
    -h, --help           show this help message and exit
    --help-all           show help for all available plugins and exit
    --directory PATH     serving directory (default: /my/current/path)
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

Browsepy app config is available at `browsepy.app.config`.

**Note**: After editing `PLUGIN_MODULES` value, plugin manager (available at
module plugin_manager and app.extensions['plugin_manager']) should be reloaded
using `plugin_manager.reload` method.

Alternatively, plugins can be loaded programmatically by calling
`plugin_manager.load_plugin` method.

More information at http://ergoithz.github.io/browsepy/integrations.html

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
