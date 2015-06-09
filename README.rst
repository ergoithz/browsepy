browsepy
========

.. image:: http://img.shields.io/travis/ergoithz/browsepy.svg?style=flat-square
  :target: https://travis-ci.org/ergoithz/browsepy
  :alt: Build status

.. image:: http://img.shields.io/coveralls/ergoithz/browsepy.svg?style=flat-square
  :target: https://coveralls.io/r/ergoithz/browsepy
  :alt: Test coverage

.. image:: http://img.shields.io/pypi/l/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: License

.. image:: http://img.shields.io/pypi/v/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Latest Version

.. image:: http://img.shields.io/pypi/dm/browsepy.svg?style=flat-square
  :target: https://pypi.python.org/pypi/browsepy/
  :alt: Downloads

.. image:: http://img.shields.io/badge/python-2.7+,_3.3+-FFC100.svg?style=flat-square
  :alt: Python 2.7+, 3.3+

Simple web file browser using flask

Features
--------

* **Simple**, like Python's SimpleHTTPServer or Apache's Directory Listing.
* **Downloadable directories**, streaming tarballs on the fly.
* **Optional remove**, which can be enabled for files under a given path.

Install
-------

It's on `pypi` so...

.. _pypi: https://pypi.python.org/pypi/browsepy/

.. code-block:: bash
    pip install browsepy

Usage
-----

Serving $HOME/shared to all addresses

.. code-block:: bash
  python -m browsepy 0.0.0.0 8080 --directory $HOME/shared

Showing help

.. code-block:: bash
  python -m browsepy --help

Screenshots
-----------

.. image:: https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png
  :target: https://raw.githubusercontent.com/ergoithz/browsepy/master/doc/screenshot.0.3.1-0.png
  :alt: Screenshot of directory with enabled remove
