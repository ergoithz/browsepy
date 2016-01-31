browsepy
========

.. image:: http://img.shields.io/travis/ergoithz/browsepy.svg?style=flat-square
  :target: https://travis-ci.org/ergoithz/browsepy
  :alt: Build status

.. image:: http://img.shields.io/coveralls/ergoithz/browsepy.svg?style=flat-square
  :target: https://coveralls.io/r/ergoithz/browsepy
  :alt: Test coverage

.. image:: https://img.shields.io/scrutinizer/g/ergoithz/browsepy.svg?style=flat-square
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
  :alt: Python 2.7+, 3.3+

Simple web file browser using flask

Features
--------

* **Simple**, like Python's SimpleHTTPServer or Apache's Directory Listing.
* **Downloadable directories**, streaming tarballs on the fly.
* **Optional remove** for files under given path.
* **Optional upload** for directories under given path.
* **Player** a simple player plugin is provided (without transcoding).

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

   python -m browsepy 0.0.0.0 8080 --directory $HOME/shared

Showing help

.. code-block:: bash

   python -m browsepy --help

Command-line arguments
----------------------

* **--directory=PATH** : directory will be served, defaults to current path
* **--initial=PATH** : starting directory, defaults to **--directory**
* **--removable=PATH** : directory where remove will be available, disabled by default
* **--upload=PATH** : directory where upload will be available, disabled by default
* **--plugins=PLUGIN_LIST** : comma-separated plugin modules
* **--debug** : enable debug mode

Using as library
----------------

It's a python module, so you can import **browsepy**, mount **app**, and serve
it (it's wsgi compliant) using your preferred server.

Browsepy is a Flask application, so it can be served along with any wsgi app
just setting **APPLICATION_ROOT** in **browsepy.app** config to browsepy prefix
url, and mounting **browsepy.app** on the appropriate parent *url-resolver*/*router*.

Browsepy app config (available at browsepy.app.config) provides the following
configuration options.

* **directory_base**, directory will be served
* **directory_start**, starting directory
* **directory_remove**, directory where remove will be available, defaults to **None**
* **directory_upload**, directory where upload will be available, defaults to **None**
* **directory_tar_buffsize**, directory tar streaming buffer size (must be multiple of 512), defaults to **262144**
* **directory_downloadable** whether enable directory download or not, defaults to **True**
* **use_binary_multiples** wheter use binary units (-bibytes, like KiB) or not (bytes, like KB), defaults to **True**
* **plugin_modules** module names (absolute or relative to plugin_namespaces) which comply the plugin spec
* **plugin_namespaces** namespaces where relative plugin_modules are searched

Plugins
-------

Starting from version 0.4.0, browsepy is extensible via plugins. An functional 'player' plugin is provided as example,
and some more are planned.

Plugins are able to load Javascript and CSS files on browsepy, add Flask endpoints, and add links to them on the file
browser (modifying the default link or adding buttons) based on the file mimetype. Look at tests and bundled plugins
for reference.

Screenshots
-----------

.. image:: https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png
  :target: https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png
  :alt: Screenshot of directory with enabled remove
