.. _quickstart:

Quickstart
==========

.. _quickstart-installation:

Installation
------------

browsepy is available at the `Python Package Index <https://pypi.python.org/>`_
so you can use pip to install. Please remember `virtualenv`_ or :mod:`venv`
usage, for Python 2 and Python 3 respectively, is highly recommended when
working with pip.

.. code-block:: bash

  pip install browsepy

Alternatively, you can get the development version from our
`github repository`_ using `git`_. Brench **master** will be
pointing to current release while new versions will reside on
their own branches.

.. code-block:: bash

  pip install git+https://github.com/ergoithz/browsepy.git

.. _virtualenv: https://virtualenv.pypa.io/
.. _github repository: https://github.com/ergoithz/browsepy
.. _git: https://git-scm.com/

.. _quickstart-usage:

Usage
-----

These examples assume python's `bin` directory is in `PATH`, if not,
replace `browsepy` with `python -m browsepy`.

Serving ``$HOME/shared`` to all addresses:

.. code-block:: bash

  browsepy 0.0.0.0 8080 --directory $HOME/shared

Showing help:

.. code-block:: bash

  browsepy --help

And this is what is printed when you run `browsepy --help`, keep in
mind that plugins (loaded with `plugin` argument) could add extra arguments to
this list.

::

  usage: browsepy [-h] [--directory PATH] [--initial PATH]
                  [--removable PATH] [--upload PATH]
                  [--exclude PATTERN] [--exclude-from PATH]
                  [--plugin MODULE]
                  [host] [port]

  description: starts a browsepy web file browser

  positional arguments:
    host                 address to listen (default: 127.0.0.1)
    port                 port to listen (default: 8080)

  optional arguments:
    -h, --help           show this help message and exit
    --directory PATH     serving directory (default: current path)
    --initial PATH       default directory (default: same as --directory)
    --removable PATH     base directory allowing remove (default: none)
    --upload PATH        base directory allowing upload (default: none)
    --exclude PATTERN    exclude paths by pattern (multiple)
    --exclude-from PATH  exclude paths by pattern file (multiple)
    --plugin MODULE      load plugin module (multiple)

Showing help including player plugin arguments:

.. code-block:: bash

  browsepy --plugin player --help

And this is what is printed when you run `browsepy --plugin player --help`.
Please note the extra parameters below `player arguments`.

::

  usage: browsepy [-h] [--directory PATH] [--initial PATH]
                  [--removable PATH] [--upload PATH]
                  [--exclude PATTERN] [--exclude-from PATH]
                  [--plugin MODULE] [--player-directory-play]
                  [host] [port]

  description: starts a browsepy web file browser

  positional arguments:
    host                  address to listen (default: 127.0.0.1)
    port                  port to listen (default: 8080)

  optional arguments:
    -h, --help            show this help message and exit
    --directory PATH      serving directory (default: current path)
    --initial PATH        default directory (default: same as --directory)
    --removable PATH      base directory allowing remove (default: none)
    --upload PATH         base directory allowing upload (default: none)
    --exclude PATTERN     exclude paths by pattern (multiple)
    --exclude-from PATH   exclude paths by pattern file (multiple)
    --plugin MODULE       load plugin module (multiple)

  player arguments:
    --player-directory-play
                          enable directories as playlist
